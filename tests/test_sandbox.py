import pytest
import json
from pathlib import Path
from autopoiesis.sandbox.executor import SandboxExecutor


def test_sandbox_timeout_scaling():
    # 0 bytes payload => 5.0 seconds base timeout
    assert SandboxExecutor.calculate_timeout(0) == 5.0
    # 1 MB payload (1048576 bytes) => 5.0 + 2.0 = 7.0 seconds
    assert SandboxExecutor.calculate_timeout(1048576) == 7.0


def test_sandbox_execution_success():
    code = """
def main(inputs: dict) -> dict:
    return {"message": f"Hello, {inputs.get('name', 'world')}!"}
"""
    res = SandboxExecutor.execute_skill_code(code, {"name": "Autopoiesis"})
    assert res.success is True
    assert res.output_payload == {"message": "Hello, Autopoiesis!"}


def test_sandbox_payload_thresholding(tmp_path: Path):
    # Small payload < 100 KB
    small_data = {"key": "value"}
    res_small = SandboxExecutor.process_payload_for_storage(small_data, tmp_path, "exec1", "node1")
    assert res_small == small_data

    # Large payload >= 100 KB
    large_data = {"key": "x" * (105 * 1024)}
    res_large = SandboxExecutor.process_payload_for_storage(large_data, tmp_path, "exec1", "node2")
    assert "_storage_type" in res_large
    assert res_large["_storage_type"] == "file"

    # Hydrate back
    hydrated = SandboxExecutor.hydrate_payload_from_storage(res_large)
    assert hydrated == large_data
