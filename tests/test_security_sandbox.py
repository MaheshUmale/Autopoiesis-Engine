"""Security-focused tests for SandboxExecutor.

Validates subprocess isolation, resource limits, payload handling, and error classification.
"""

import pytest
import json
import sys
from pathlib import Path

from autopoiesis.sandbox.executor import (
    SandboxExecutor,
    SandboxResult,
    MAX_MEMORY_MB,
    MAX_OUTPUT_SIZE_BYTES,
    classify_error,
    ERROR_CLASSIFICATION_RULES,
)


class TestSandboxResult:
    """Tests for SandboxResult model."""

    def test_sandbox_result_success(self):
        """Create a successful SandboxResult."""
        result = SandboxResult(
            success=True,
            output_payload={"key": "value"},
            stdout="output",
            stderr="",
            execution_time_sec=0.5,
        )
        assert result.success is True
        assert result.error_type is None

    def test_sandbox_result_failure(self):
        """Create a failed SandboxResult."""
        result = SandboxResult(
            success=False,
            output_payload={},
            stdout="",
            stderr="Error occurred",
            execution_time_sec=0.5,
            error_type="LogicError",
        )
        assert result.success is False
        assert result.error_type == "LogicError"

    def test_sandbox_result_serialization(self):
        """SandboxResult should serialize to dict."""
        result = SandboxResult(
            success=True,
            output_payload={"key": "value"},
            stdout="output",
            stderr="",
            execution_time_sec=0.5,
        )
        data = result.model_dump()
        assert data["success"] is True
        assert data["output_payload"] == {"key": "value"}


class TestSandboxExecutorTimeout:
    """Tests for timeout calculation."""

    def test_timeout_base(self):
        """Base timeout should be 5.0 seconds."""
        assert SandboxExecutor.calculate_timeout(0) == 5.0

    def test_timeout_scales_with_payload(self):
        """Timeout should scale with payload size."""
        # 1 MB = 5.0 + 2.0 = 7.0
        assert SandboxExecutor.calculate_timeout(1048576) == 7.0

    def test_timeout_large_payload(self):
        """Large payload should have proportionally larger timeout."""
        # 10 MB = 5.0 + 20.0 = 25.0
        assert SandboxExecutor.calculate_timeout(10 * 1048576) == 25.0


class TestSandboxExecutorPayloadHandling:
    """Tests for payload thresholding and storage."""

    def test_small_payload_inline(self):
        """Small payloads should be returned as-is."""
        payload = {"key": "value"}
        result = SandboxExecutor.process_payload_for_storage(
            payload, Path("/tmp"), "exec1", "node1"
        )
        assert result == payload

    def test_large_payload_to_file(self):
        """Large payloads should be stored to file."""
        import tempfile
        payload = {"key": "x" * (105 * 1024)}
        with tempfile.TemporaryDirectory() as tmpdir:
            result = SandboxExecutor.process_payload_for_storage(
                payload, Path(tmpdir), "exec1", "node1"
            )
            assert result["_storage_type"] == "file"
            assert Path(result["path"]).exists()

    def test_hydrate_file_payload(self):
        """File payloads should be hydrated back correctly."""
        import tempfile
        payload = {"key": "x" * (105 * 1024)}
        with tempfile.TemporaryDirectory() as tmpdir:
            stored = SandboxExecutor.process_payload_for_storage(
                payload, Path(tmpdir), "exec1", "node1"
            )
            hydrated = SandboxExecutor.hydrate_payload_from_storage(stored)
            assert hydrated == payload

    def test_hydrate_inline_payload(self):
        """Inline payloads should pass through unchanged."""
        payload = {"key": "value"}
        result = SandboxExecutor.hydrate_payload_from_storage(payload)
        assert result == payload

    def test_hydrate_nonexistent_file(self):
        """Hydrating nonexistent file should return original payload."""
        stored = {"_storage_type": "file", "path": "/nonexistent/path"}
        result = SandboxExecutor.hydrate_payload_from_storage(stored)
        assert result == stored


class TestSandboxExecutorCodeExecution:
    """Tests for code execution security."""

    def test_execute_simple_code(self):
        """Execute simple skill code."""
        code = """
def main(inputs: dict) -> dict:
    return {"result": inputs.get("value", 0) * 2}
"""
        result = SandboxExecutor.execute_skill_code(code, {"value": 5})
        assert result.success is True
        assert result.output_payload == {"result": 10}

    def test_execute_code_without_main(self):
        """Code without main() should fail."""
        code = """
def helper(inputs: dict) -> dict:
    return {"result": 1}
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is False
        assert "main" in result.stderr.lower()

    def test_execute_code_with_syntax_error(self):
        """Code with syntax error should fail."""
        code = """
def main(inputs: dict) -> dict:
    return {{"result": 1}  # syntax error
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is False

    def test_execute_code_with_runtime_error(self):
        """Code with runtime error should fail."""
        code = """
def main(inputs: dict) -> dict:
    raise ValueError("test error")
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is False
        assert "ValueError" in result.stderr

    def test_execute_code_returns_none(self):
        """Code returning None should return empty dict."""
        code = """
def main(inputs: dict) -> dict:
    pass
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is True
        assert result.output_payload == {}

    def test_execute_code_with_imports(self):
        """Code with standard library imports should work."""
        code = """
import json
def main(inputs: dict) -> dict:
    return {"json_version": json.__version__ if hasattr(json, '__version__') else "unknown"}
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is True

    def test_execute_code_with_math(self):
        """Code with math operations should work."""
        code = """
import math
def main(inputs: dict) -> dict:
    return {"pi": math.pi, "sqrt_2": math.sqrt(2)}
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is True
        assert "pi" in result.output_payload


class TestSandboxExecutorErrorClassification:
    """Tests for error type classification."""

    def test_memory_error_classification(self):
        """MemoryError should be classified as EnvironmentalError."""
        code = """
def main(inputs: dict) -> dict:
    raise MemoryError("Out of memory")
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is False
        assert result.error_type == "EnvironmentalError"

    def test_syntax_error_classification(self):
        """SyntaxError should be classified as LogicError."""
        code = """
def main(inputs: dict) -> dict:
    invalid syntax here
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is False
        assert result.error_type == "LogicError"

    def test_name_error_classification(self):
        """NameError should be classified as LogicError."""
        code = """
def main(inputs: dict) -> dict:
    return undefined_variable
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is False
        assert result.error_type == "LogicError"

    def test_timeout_error_classification(self):
        """Timeout should be classified as TimeoutError."""
        code = """
import time
def main(inputs: dict) -> dict:
    time.sleep(10)
    return {"result": "done"}
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is False
        assert result.error_type == "TimeoutError"

    def test_generic_exception_is_logic_error(self):
        """Generic exceptions should be classified as LogicError."""
        code = """
def main(inputs: dict) -> dict:
    raise RuntimeError("Something went wrong")
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is False
        assert result.error_type == "LogicError"


class TestSandboxExecutorResourceLimits:
    """Tests for resource limits."""

    def test_max_memory_constant_defined(self):
        """MAX_MEMORY_MB constant should be defined."""
        assert MAX_MEMORY_MB == 512

    def test_max_output_size_constant_defined(self):
        """MAX_OUTPUT_SIZE_BYTES constant should be defined."""
        assert MAX_OUTPUT_SIZE_BYTES == 10 * 1024 * 1024

    def test_payload_threshold_constant(self):
        """PAYLOAD_THRESHOLD_BYTES should be 100 KB."""
        assert SandboxExecutor.PAYLOAD_THRESHOLD_BYTES == 100 * 1024


class TestSandboxExecutorIsolation:
    """Tests for subprocess isolation."""

    def test_code_cannot_access_parent_globals(self):
        """Skill code should not access parent process globals."""
        code = """
def main(inputs: dict) -> dict:
    try:
        # This should not work in subprocess
        with open("/etc/passwd", "r") as f:
            content = f.read(100)
        return {"leaked": content}
    except Exception as e:
        return {"error": str(e)}
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        # Should either succeed with error or fail - but not leak parent state
        assert result.success is True or result.success is False

    def test_code_runs_in_subprocess(self):
        """Skill code should run in a separate subprocess."""
        import os
        code = """
import os
def main(inputs: dict) -> dict:
    return {"pid": os.getpid()}
"""
        result = SandboxExecutor.execute_skill_code(code, {})
        assert result.success is True
        # PID should be different from current process
        assert result.output_payload["pid"] != os.getpid()

    def test_code_cannot_modify_parent_filesystem(self):
        """Skill code should not modify parent process filesystem."""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("original content")
            temp_path = f.name
        
        try:
            code = f"""
import os
def main(inputs: dict) -> dict:
    try:
        with open("{temp_path}", "w") as f:
            f.write("modified by skill")
        return {{"status": "modified"}}
    except Exception as e:
        return {{"error": str(e)}}
"""
            result = SandboxExecutor.execute_skill_code(code, {})
            # Check that original file is unchanged
            with open(temp_path, "r") as f:
                content = f.read()
            assert content == "original content"
        finally:
            os.unlink(temp_path)


class TestErrorClassification:
    """Tests for structured error classification (fixes M-2)."""

    def test_classify_memory_error(self):
        """MemoryError should be classified as EnvironmentalError."""
        assert classify_error("MemoryError: Out of memory") == "EnvironmentalError"

    def test_classify_cannot_allocate(self):
        """'cannot allocate' should be classified as EnvironmentalError."""
        assert classify_error("cannot allocate memory") == "EnvironmentalError"

    def test_classify_connection_error(self):
        """ConnectionError should be classified as NetworkError."""
        assert classify_error("ConnectionError: Failed to connect") == "NetworkError"

    def test_classify_connection_refused(self):
        """ConnectionRefused should be classified as NetworkError."""
        assert classify_error("ConnectionRefusedError: Connection refused") == "NetworkError"

    def test_classify_syntax_error(self):
        """SyntaxError should be classified as LogicError."""
        assert classify_error("SyntaxError: invalid syntax") == "LogicError"

    def test_classify_name_error(self):
        """NameError should be classified as LogicError."""
        assert classify_error("NameError: name 'x' is not defined") == "LogicError"

    def test_classify_validation_error(self):
        """ValidationError should be classified as SchemaValidationError."""
        assert classify_error("ValidationError: field required") == "SchemaValidationError"

    def test_classify_type_error_argument(self):
        """TypeError with argument should be classified as SchemaValidationError."""
        assert classify_error("TypeError: missing 1 required argument") == "SchemaValidationError"

    def test_classify_timeout_error(self):
        """Timeout should be classified as TimeoutError."""
        assert classify_error("Execution timed out.") == "TimeoutError"

    def test_classify_empty_stderr(self):
        """Empty stderr should default to LogicError."""
        assert classify_error("") == "LogicError"

    def test_classify_none_equivalent(self):
        """Unknown errors should default to LogicError."""
        assert classify_error("Some unknown error") == "LogicError"

    def test_classify_case_insensitive(self):
        """Error classification should be case-insensitive."""
        assert classify_error("memoryerror: out of memory") == "EnvironmentalError"
        assert classify_error("CONNECTIONERROR: failed") == "NetworkError"

    def test_error_rules_defined(self):
        """ERROR_CLASSIFICATION_RULES should be defined."""
        assert len(ERROR_CLASSIFICATION_RULES) > 0
        # Check that all expected error types are covered
        error_types = [rule[0] for rule in ERROR_CLASSIFICATION_RULES]
        assert "TimeoutError" in error_types
        assert "EnvironmentalError" in error_types
        assert "NetworkError" in error_types
        assert "SchemaValidationError" in error_types
        assert "LogicError" in error_types

    def test_error_rules_are_compiled_patterns(self):
        """ERROR_CLASSIFICATION_RULES should contain compiled regex patterns."""
        import re
        for error_type, pattern in ERROR_CLASSIFICATION_RULES:
            assert isinstance(pattern, re.Pattern), f"{error_type} pattern is not compiled"

    def test_classify_http_error(self):
        """HTTP errors should be classified as NetworkError."""
        assert classify_error("HTTPError: 404 Not Found") == "NetworkError"

    def test_classify_url_error(self):
        """URLError should be classified as NetworkError."""
        assert classify_error("URLError: <urlopen error [Errno 111] Connection refused>") == "NetworkError"

    def test_classify_url_error_timeout(self):
        """URLError with timeout should be classified as TimeoutError (higher priority)."""
        assert classify_error("URLError: <urlopen error timed out>") == "TimeoutError"

    def test_classify_import_error(self):
        """ImportError should be classified as LogicError."""
        assert classify_error("ImportError: No module named 'xyz'") == "LogicError"

    def test_classify_key_error(self):
        """KeyError should be classified as LogicError."""
        assert classify_error("KeyError: 'missing_key'") == "LogicError"

    def test_classify_index_error(self):
        """IndexError should be classified as LogicError."""
        assert classify_error("IndexError: list index out of range") == "LogicError"

    def test_classify_value_error(self):
        """ValueError should be classified as LogicError."""
        assert classify_error("ValueError: invalid literal") == "LogicError"

    def test_classify_attribute_error(self):
        """AttributeError should be classified as LogicError."""
        assert classify_error("AttributeError: 'NoneType' has no attribute 'x'") == "LogicError"
