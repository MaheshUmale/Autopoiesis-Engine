import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict
from pydantic import BaseModel

import pyarrow as pa
import pyarrow.parquet as pq

from autopoiesis.core.platform import PlatformAdapter


class SandboxResult(BaseModel):
    success: bool
    output_payload: Dict[str, Any]
    stdout: str
    stderr: str
    execution_time_sec: float
    error_type: str | None = None  # SchemaValidationError, LogicError, TimeoutError, EnvironmentalError, NetworkError


class SandboxExecutor:
    """Executes micro-skills in an isolated environment with dynamic timeout scaling and payload thresholding."""

    PAYLOAD_THRESHOLD_BYTES = 100 * 1024  # 100 KB limit for inline payloads

    @staticmethod
    def calculate_timeout(payload_bytes: int) -> float:
        """Calculates dynamic timeout formula: Timeout_total = 5.0 + (Payload_bytes / 1048576 * 2.0)."""
        payload_mb = payload_bytes / 1048576.0
        return 5.0 + (payload_mb * 2.0)

    @classmethod
    def process_payload_for_storage(cls, payload: Dict[str, Any], staging_dir: Path, execution_id: str, node_id: str) -> Dict[str, Any]:
        """Enforces 100 KB payload boundary rule.

        If payload size >= 100 KB, serializes to Parquet staging file and returns a file pointer.
        """
        raw_json = json.dumps(payload)
        payload_bytes = len(raw_json.encode("utf-8"))

        if payload_bytes < cls.PAYLOAD_THRESHOLD_BYTES:
            return payload

        # Payload is >= 100 KB -> Store to Parquet
        staging_dir.mkdir(parents=True, exist_ok=True)
        file_path = staging_dir / f"{execution_id}_{node_id}.parquet"

        # Convert dictionary payload to arrow table
        # Store JSON wrapped in Arrow schema for universal restoration
        schema = pa.schema([('data', pa.string())])
        table = pa.Table.from_batches([
            pa.RecordBatch.from_arrays([pa.array([raw_json])], schema=schema)
        ])
        pq.write_table(table, str(file_path))

        return {
            "_storage_type": "file",
            "path": str(file_path.resolve())
        }

    @classmethod
    def hydrate_payload_from_storage(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Hydrates a file pointer payload back into memory if storage_type == 'file'."""
        if isinstance(payload, dict) and payload.get("_storage_type") == "file" and "path" in payload:
            file_path = Path(payload["path"])
            if file_path.exists():
                table = pq.read_table(str(file_path))
                raw_json = table.column('data')[0].as_py()
                return json.loads(raw_json)
        return payload

    @classmethod
    def execute_skill_code(
        cls,
        python_code: str,
        input_payload: Dict[str, Any],
        cwd: Path | str | None = None
    ) -> SandboxResult:
        """Executes a micro-skill's Python code in a sandboxed subprocess.

        The code is expected to define a `main(inputs: dict) -> dict` function.
        """
        # Hydrate input payload if it's a file pointer
        hydrated_input = cls.hydrate_payload_from_storage(input_payload)
        input_bytes = len(json.dumps(hydrated_input).encode("utf-8"))
        timeout = cls.calculate_timeout(input_bytes)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            script_file = temp_path / "runner.py"
            input_file = temp_path / "input.json"
            output_file = temp_path / "output.json"

            input_file.write_text(json.dumps(hydrated_input), encoding="utf-8")

            # Harness wrapper to execute main() safely without f-string interpolation issues
            harness_prefix = """import json
import sys

"""
            harness_suffix = f"""

if __name__ == "__main__":
    try:
        with open("{input_file.name}", "r", encoding="utf-8") as f:
            inputs = json.load(f)

        if "main" not in globals():
            raise AttributeError("Skill code does not define a 'main(inputs)' entrypoint function.")

        result = main(inputs)

        with open("{output_file.name}", "w", encoding="utf-8") as f:
            json.dump(result if result is not None else {{}}, f)
    except Exception as e:
        import traceback
        sys.stderr.write(traceback.format_exc())
        sys.exit(1)
"""
            harness_code = harness_prefix + python_code + harness_suffix
            script_file.write_text(harness_code, encoding="utf-8")

            import time
            start_time = time.time()

            try:
                proc = PlatformAdapter.run_command(
                    f"{sys.executable} runner.py",
                    cwd=temp_path,
                    timeout=timeout,
                )
                exec_time = time.time() - start_time

                if proc.returncode != 0:
                    stderr = proc.stderr.strip()
                    error_type = "LogicError"
                    if "ValidationError" in stderr or "TypeError" in stderr and "argument" in stderr:
                        error_type = "SchemaValidationError"
                    elif "SyntaxError" in stderr or "NameError" in stderr or "AttributeError" in stderr:
                        error_type = "LogicError"
                    elif "HTTP" in stderr or "ConnectionError" in stderr:
                        error_type = "NetworkError"
                    elif "MemoryError" in stderr:
                        error_type = "EnvironmentalError"

                    return SandboxResult(
                        success=False,
                        output_payload={},
                        stdout=proc.stdout,
                        stderr=stderr,
                        execution_time_sec=exec_time,
                        error_type=error_type,
                    )

                output_payload = {}
                if output_file.exists():
                    try:
                        output_payload = json.loads(output_file.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        output_payload = {}

                return SandboxResult(
                    success=True,
                    output_payload=output_payload,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    execution_time_sec=exec_time,
                )

            except subprocess.TimeoutExpired as e:
                exec_time = time.time() - start_time
                return SandboxResult(
                    success=False,
                    output_payload={},
                    stdout=e.stdout.decode() if e.stdout else "",
                    stderr="Execution timed out.",
                    execution_time_sec=exec_time,
                    error_type="TimeoutError",
                )
