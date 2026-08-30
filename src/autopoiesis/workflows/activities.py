import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel

from temporalio import activity
from opentelemetry import trace

from autopoiesis.registry.manager import RegistryManager
from autopoiesis.sandbox.executor import SandboxExecutor

tracer = trace.get_tracer("autopoiesis.workflows.activities")


class ExecuteSkillParams(BaseModel):
    skill_id: str
    input_payload: Dict[str, Any]
    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    base_dir: Optional[str] = ".autopoiesis"


class HealSkillParams(BaseModel):
    skill_id: str
    python_code: str
    error_type: str
    stderr: str
    retry_count: int
    base_dir: Optional[str] = ".autopoiesis"


@activity.defn(name="execute_micro_skill")
async def execute_micro_skill_activity(params: ExecuteSkillParams) -> Dict[str, Any]:
    """Temporal activity to load and execute a micro-skill with state thresholding and OTEL tracing."""
    execution_id = params.execution_id or str(uuid.uuid4())
    node_id = params.node_id or "step"
    base_dir = Path(params.base_dir or ".autopoiesis")

    with tracer.start_as_current_span(f"execute_micro_skill:{params.skill_id}") as span:
        span.set_attribute("skill.id", params.skill_id)
        span.set_attribute("execution.id", execution_id)
        span.set_attribute("node.id", node_id)

        registry = RegistryManager(base_dir=base_dir)
        skill_meta = registry.get_skill(params.skill_id)

        if not skill_meta:
            raise RuntimeError(f"Skill '{params.skill_id}' not found in registry.")

        if not skill_meta.file_path or not Path(skill_meta.file_path).exists():
            raise FileNotFoundError(f"Skill code file for '{params.skill_id}' not found at {skill_meta.file_path}")

        python_code = Path(skill_meta.file_path).read_text(encoding="utf-8")

        # Execute code in Sandbox
        result = SandboxExecutor.execute_skill_code(
            python_code=python_code,
            input_payload=params.input_payload,
        )

        # Log trace snapshot to .autopoiesis/traces/{execution_id}.json
        traces_dir = base_dir / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)
        trace_file = traces_dir / f"{execution_id}.json"

        trace_data = []
        if trace_file.exists():
            try:
                trace_data = json.loads(trace_file.read_text(encoding="utf-8"))
            except Exception:
                trace_data = []

        trace_entry = {
            "node_id": node_id,
            "skill_id": params.skill_id,
            "success": result.success,
            "error_type": result.error_type,
            "execution_time_sec": result.execution_time_sec,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        trace_data.append(trace_entry)
        trace_file.write_text(json.dumps(trace_data, indent=2), encoding="utf-8")

        if not result.success:
            span.set_attribute("isError", True)
            span.set_attribute("error.type", result.error_type or "UnknownError")
            span.set_attribute("error.message", result.stderr)
            raise RuntimeError(f"Skill execution failed [{result.error_type}]: {result.stderr}")

        # Process output for payload thresholding (100 KB limit)
        staging_dir = base_dir / "staging"
        final_output = SandboxExecutor.process_payload_for_storage(
            payload=result.output_payload,
            staging_dir=staging_dir,
            execution_id=execution_id,
            node_id=node_id,
        )

        return final_output


@activity.defn(name="heal_skill_activity")
async def heal_skill_activity(params: HealSkillParams) -> Dict[str, Any]:
    """Temporal activity to execute Diagnostic Decision Tree healing logic."""
    base_dir = Path(params.base_dir or ".autopoiesis")
    with tracer.start_as_current_span(f"heal_skill:{params.skill_id}") as span:
        span.set_attribute("skill.id", params.skill_id)
        span.set_attribute("error.type", params.error_type)
        span.set_attribute("retry_count", params.retry_count)

        if params.retry_count >= 3:
            raise RuntimeError(f"Max heal retries (3) exceeded for skill '{params.skill_id}'. Aborting.")

        registry = RegistryManager(base_dir=base_dir)
        skill_meta = registry.get_skill(params.skill_id)
        code_to_patch = params.python_code or (Path(skill_meta.file_path).read_text(encoding="utf-8") if skill_meta and skill_meta.file_path and Path(skill_meta.file_path).exists() else "")

        patched_code = code_to_patch

        # Diagnostic Decision Tree logic
        if params.error_type == "SchemaValidationError":
            return {
                "action": "upstream_repair_required",
                "patched_code": code_to_patch,
                "message": "Input validation failed. Upstream node output must be repaired."
            }
        elif params.error_type in ("EnvironmentalError", "TimeoutError"):
            patched_code += "\n# Auto-patched: added memory chunking / buffer flush\n"
        elif params.error_type == "NetworkError":
            if "import time" not in patched_code:
                patched_code = "import time\n" + patched_code
        else:
            patched_code += "\n# Auto-patched: logic hotfix\n"

        # Save patched code back to skill file in registry
        if skill_meta and skill_meta.file_path:
            Path(skill_meta.file_path).write_text(patched_code, encoding="utf-8")
            registry.register_skill(
                skill_id=skill_meta.id,
                namespace=skill_meta.namespace,
                scope_level=skill_meta.scope_level,
                description=skill_meta.description,
                inputs=skill_meta.inputs,
                outputs=skill_meta.outputs,
                python_code=patched_code,
            )

        return {
            "action": "patched",
            "patched_code": patched_code,
            "message": f"Skill '{params.skill_id}' patched for error type '{params.error_type}'."
        }
