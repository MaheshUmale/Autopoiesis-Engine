import uuid
from datetime import timedelta
from typing import Any, Dict, List
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from autopoiesis.workflows.activities import (
        ExecuteSkillParams,
        HealSkillParams,
        execute_micro_skill_activity,
        heal_skill_activity,
    )


@workflow.defn(name="SelfHealingWorkflow")
class SelfHealingWorkflow:
    """Workflow to attempt diagnostic repairing of a failed skill up to 3 times."""

    @workflow.run
    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        retry_count = params.get("retry_count", 0)
        if retry_count >= 3:
            return {
                "healed": False,
                "reason": "Max retry limit (3) exceeded."
            }

        heal_params = HealSkillParams(
            skill_id=params["skill_id"],
            python_code=params.get("python_code", ""),
            error_type=params.get("error_type", "LogicError"),
            stderr=params.get("stderr", ""),
            retry_count=retry_count,
            base_dir=params.get("base_dir", ".autopoiesis"),
        )

        result = await workflow.execute_activity(
            heal_skill_activity,
            heal_params,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        return result


@workflow.defn(name="AutopoiesisDAGWorkflow")
class AutopoiesisDAGWorkflow:
    """Deterministic Temporal DAG Workflow for executing synthesized composite templates."""

    @workflow.run
    async def run(self, dag_template: Dict[str, Any], initial_parameters: Dict[str, Any] | None = None) -> Dict[str, Any]:
        execution_id = workflow.info().workflow_id
        parameters = initial_parameters or dag_template.get("parameters", {})
        dag = dag_template.get("dag", {})
        nodes: List[Dict[str, Any]] = dag.get("nodes", [])

        node_outputs: Dict[str, Any] = {}

        for node in nodes:
            node_id = node["id"]
            skill_id = node["skill_id"]
            raw_args = node.get("args", {})

            # Parameter resolution (simple mustache-style string template replacing)
            resolved_args = self._resolve_node_args(raw_args, parameters, node_outputs)

            exec_params = ExecuteSkillParams(
                skill_id=skill_id,
                input_payload=resolved_args,
                execution_id=execution_id,
                node_id=node_id,
            )

            # Execute activity with Self-Healing Loop up to 3 attempts
            executed_successfully = False
            for retry_count in range(3):
                try:
                    output = await workflow.execute_activity(
                        execute_micro_skill_activity,
                        exec_params,
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RetryPolicy(
                            initial_interval=timedelta(seconds=1),
                            maximum_interval=timedelta(seconds=5),
                            maximum_attempts=1,
                        ),
                    )
                    node_outputs[node_id] = output
                    executed_successfully = True
                    break
                except Exception as e:
                    # Route failure to Self-Healing Workflow
                    heal_res = await workflow.execute_child_workflow(
                        SelfHealingWorkflow.run,
                        {
                            "skill_id": skill_id,
                            "error_type": "LogicError",
                            "stderr": str(e),
                            "retry_count": retry_count,
                        },
                        id=f"heal_{execution_id}_{node_id}_{retry_count}",
                    )
                    if heal_res.get("action") != "patched" or retry_count == 2:
                        raise RuntimeError(f"DAG execution failed at node '{node_id}' ({skill_id}): {e}. Healing result: {heal_res}")

            if not executed_successfully:
                raise RuntimeError(f"Node '{node_id}' ({skill_id}) failed after max self-healing retries.")

        return node_outputs

    def _resolve_node_args(
        self,
        raw_args: Dict[str, Any],
        parameters: Dict[str, Any],
        node_outputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Helper to resolve templates in node inputs."""
        resolved = {}
        for key, value in raw_args.items():
            if isinstance(value, str):
                val_str = value.strip()
                # Check for parameter injection: {{ parameters.foo }}
                if val_str.startswith("{{ parameters.") and val_str.endswith("}}"):
                    param_key = val_str[14:-2].strip()
                    resolved[key] = parameters.get(param_key)
                # Check for step output injection: {{ step_1.output }} or {{ step_1.output.bar }}
                elif val_str.startswith("{{") and val_str.endswith("}}"):
                    expr = val_str[2:-2].strip()
                    parts = expr.split(".")
                    step_id = parts[0]
                    step_val = node_outputs.get(step_id, {})
                    if len(parts) > 1 and parts[1] == "output":
                        if len(parts) > 2 and isinstance(step_val, dict):
                            resolved[key] = step_val.get(parts[2])
                        else:
                            resolved[key] = step_val
                    else:
                        resolved[key] = step_val
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved
