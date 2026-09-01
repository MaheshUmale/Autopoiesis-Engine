"""AMF Orchestrator — DAG-based multi-agent composition wrapper.

Fixes:
- GAP-L4: Orchestrator retry now applies actual fix
- N-3: Removed dead code (unused invoke_skill call)
- N-1: EventEmitter integration for workflow events
- AC-2: Uses shared healing utility from PipelineExecutor
"""

import uuid
import logging
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.core.events import EventEmitter, Event, SystemEvents
from autopoiesis.registry.manager import RegistryManager
from autopoiesis.workflows.dag import AutopoiesisDAGWorkflow
from autopoiesis.workflows.activities import ExecuteSkillParams, HealSkillParams
from autopoiesis.amf.registry import AMFRegistry
from autopoiesis.amf.runtime import AMFRuntime, InvocationResult
from autopoiesis.amf.bus import AMFBusAdapter
from autopoiesis.amf.schema import WorkflowDef, WorkflowNode, WorkflowEdge, AgentDef
from autopoiesis.mcp.pipeline import PipelineExecutor

logger = logging.getLogger("autopoiesis.amf.orchestrator")


class WorkflowExecutionResult(BaseModel):
    """Result of a workflow execution."""
    workflow_id: str
    success: bool
    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    execution_time_sec: float = 0.0


class AMFOrchestrator:
    """Wraps AutopoiesisDAGWorkflow for AMF-native multi-agent composition.

    Accepts WorkflowDef from AMF manifests and:
    - Resolves agent IDs to capability invocations via AMFRuntime
    - Manages inter-agent data flow via AMFBusAdapter
    - Applies self-healing via AMFHealingAdapter
    """

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self._registry = AMFRegistry(base_dir=base_dir)
        self._runtime = AMFRuntime(base_dir=base_dir)
        self._bus = AMFBusAdapter(base_dir=base_dir)
        self._healing = None  # lazy init
        # EventEmitter integration (N-1)
        self._events = EventEmitter(base_dir=base_dir)
        self._executions: Dict[str, WorkflowExecutionResult] = {}

    def _get_healing(self):
        if self._healing is None:
            from autopoiesis.amf.healing import AMFHealingAdapter
            self._healing = AMFHealingAdapter(base_dir=self.base_dir)
        return self._healing

    def run_workflow(
        self,
        workflow_def: WorkflowDef,
        parameters: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
    ) -> WorkflowExecutionResult:
        """Executes a workflow DAG.

        Args:
            workflow_def: Workflow definition
            parameters: Initial parameters for the workflow
            execution_id: Optional execution ID for tracking

        Returns:
            WorkflowExecutionResult with all node outputs
        """
        import time
        start_time = time.time()
        execution_id = execution_id or f"wf_{uuid.uuid4().hex[:12]}"
        parameters = parameters or workflow_def.parameters or {}

        # Emit workflow started event (N-1)
        self._events.emit(Event(
            event_type=SystemEvents.WORKFLOW_STARTED,
            source="AMFOrchestrator",
            payload={
                "workflow_id": workflow_def.workflow_id,
                "execution_id": execution_id,
                "node_count": len(workflow_def.nodes),
            },
        ))

        node_outputs: Dict[str, Any] = {}
        errors: List[Dict[str, Any]] = []
        node_map = {node.node_id: node for node in workflow_def.nodes}

        # Build step mapping for template resolution: step_1 -> node_id
        step_map = {}
        for i, node in enumerate(workflow_def.nodes, 1):
            step_map[f"step_{i}"] = node.node_id

        # Build adjacency list for topological execution
        in_degree: Dict[str, int] = {node.node_id: 0 for node in workflow_def.nodes}
        adjacency: Dict[str, List[str]] = {node.node_id: [] for node in workflow_def.nodes}
        for edge in workflow_def.edges:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        # Execute nodes in topological order
        queue = [nid for nid in in_degree if in_degree[nid] == 0]
        completed = set()

        while queue:
            current_id = queue.pop(0)
            if current_id not in node_map:
                continue

            node = node_map[current_id]
            node_inputs = self._resolve_node_inputs(node, parameters, node_outputs, step_map)

            # Execute node via AMF runtime
            result = self._runtime.invoke_capability(
                agent_id=node.agent_id,
                capability_name=node.capability,
                inputs=node_inputs,
            )

            if result.success:
                node_outputs[current_id] = result.output
                completed.add(current_id)

                # Deliver output to target agents via bus if needed
                for edge in workflow_def.edges:
                    if edge.source == current_id:
                        self._bus.deliver_to_agent(
                            agent_id=node_map[edge.target].agent_id,
                            message=self._bus.broadcast(
                                channel=f"amf.workflow.{workflow_def.workflow_id}.{edge.target}",
                                sender_agent=node.agent_id,
                                payload=result.output,
                                capability=node.capability,
                            ),
                        )
            else:
                error_info = {
                    "node_id": current_id,
                    "agent_id": node.agent_id,
                    "capability": node.capability,
                    "error": result.stderr,
                    "error_type": result.error_type,
                }
                errors.append(error_info)

                # Attempt healing (fixes GAP-L4: actually apply the fix)
                healing = self._get_healing()
                suggestion = healing.heal_capability_failure(
                    agent_id=node.agent_id,
                    capability=node.capability,
                    error_type=result.error_type or "LogicError",
                    error_msg=result.stderr,
                )

                # Retry with actual fix applied (fixes GAP-L4, N-3: removed dead code)
                healed = False
                if suggestion.source == "cache" and suggestion.fix_code_patch:
                    # Get the skill code and apply the fix
                    reg = self._get_skill_registry()
                    agent_def = self._registry.get_agent_def(node.agent_id)
                    if agent_def:
                        for cap in agent_def.capabilities:
                            if cap.name == node.capability:
                                skill = reg.get_skill(cap.skill_id)
                                if skill and skill.file_path:
                                    original_code = Path(skill.file_path).read_text(encoding="utf-8")
                                    # Use shared healing utility (AC-2)
                                    patched_code = PipelineExecutor.apply_fix_to_code(original_code, suggestion.fix_code_patch)
                                    # Execute with patched code
                                    from autopoiesis.sandbox.executor import SandboxExecutor
                                    enriched_inputs = dict(node_inputs)
                                    enriched_inputs["_agent_id"] = node.agent_id
                                    enriched_inputs["_capability"] = node.capability
                                    enriched_inputs["_cwd"] = str(Path.cwd())
                                    exec_res = SandboxExecutor.execute_skill_code(patched_code, enriched_inputs)
                                    if exec_res.success:
                                        node_outputs[current_id] = exec_res.output_payload
                                        completed.add(current_id)
                                        healing.record_healing_outcome(suggestion.pattern_id, success=True)
                                        healed = True
                                        # Emit healing applied event (N-1)
                                        self._events.emit(Event(
                                            event_type=SystemEvents.HEALING_APPLIED,
                                            source="AMFOrchestrator",
                                            payload={
                                                "workflow_id": workflow_def.workflow_id,
                                                "node_id": current_id,
                                                "pattern_id": suggestion.pattern_id,
                                            },
                                        ))
                                        break
                                    else:
                                        healing.record_healing_outcome(suggestion.pattern_id, success=False)
                                        # Emit healing failed event (N-1)
                                        self._events.emit(Event(
                                            event_type=SystemEvents.HEALING_FAILED,
                                            source="AMFOrchestrator",
                                            payload={
                                                "workflow_id": workflow_def.workflow_id,
                                                "node_id": current_id,
                                                "pattern_id": suggestion.pattern_id,
                                            },
                                        ))
                
                # If healing didn't work, stop workflow
                if not healed and current_id not in completed:
                    # Emit skill failed event (N-1)
                    self._events.emit(Event(
                        event_type=SystemEvents.SKILL_FAILED,
                        source="AMFOrchestrator",
                        payload={
                            "workflow_id": workflow_def.workflow_id,
                            "node_id": current_id,
                            "error": result.stderr,
                            "error_type": result.error_type,
                        },
                    ))
                    break

            # Add completed node's successors to queue if all their dependencies are met
            for edge in workflow_def.edges:
                if edge.source == current_id:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)

        exec_time = time.time() - start_time
        result = WorkflowExecutionResult(
            workflow_id=workflow_def.workflow_id,
            success=len(errors) == 0 and len(completed) == len(workflow_def.nodes),
            node_outputs=node_outputs,
            errors=errors,
            execution_time_sec=round(exec_time, 3),
        )
        self._executions[execution_id] = result

        # Emit workflow completed/failed event (N-1)
        if result.success:
            self._events.emit(Event(
                event_type=SystemEvents.WORKFLOW_COMPLETED,
                source="AMFOrchestrator",
                payload={
                    "workflow_id": workflow_def.workflow_id,
                    "execution_id": execution_id,
                    "execution_time_sec": round(exec_time, 3),
                },
            ))
        else:
            self._events.emit(Event(
                event_type=SystemEvents.WORKFLOW_FAILED,
                source="AMFOrchestrator",
                payload={
                    "workflow_id": workflow_def.workflow_id,
                    "execution_id": execution_id,
                    "errors": len(errors),
                },
            ))

        return result

    def _resolve_node_inputs(
        self,
        node: WorkflowNode,
        parameters: Dict[str, Any],
        node_outputs: Dict[str, Any],
        step_map: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Resolves node inputs with parameter and step output injection."""
        step_map = step_map or {}
        resolved = {}
        for key, value in node.inputs.items():
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
                    # Map step_N convention to actual node_id
                    actual_id = step_map.get(step_id, step_id)
                    step_val = node_outputs.get(actual_id, {})
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

    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Returns execution status for a workflow."""
        for exec_id, result in self._executions.items():
            if result.workflow_id == workflow_id:
                return {
                    "execution_id": exec_id,
                    "workflow_id": result.workflow_id,
                    "success": result.success,
                    "node_count": len(result.node_outputs),
                    "error_count": len(result.errors),
                    "execution_time_sec": result.execution_time_sec,
                    "errors": result.errors,
                }
        return None

    def run_workflow_by_id(
        self,
        workflow_id: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> WorkflowExecutionResult:
        """Looks up a workflow by ID from the registry and executes it."""
        amf_reg = self._registry
        workflow_def = amf_reg.get_workflow(workflow_id)
        if not workflow_def:
            raise ValueError(f"Workflow '{workflow_id}' not found in AMF registry. Register it first with register_workflow().")
        merged_params = dict(workflow_def.parameters or {})
        if parameters:
            merged_params.update(parameters)
        return self.run_workflow(workflow_def=workflow_def, parameters=merged_params)

    def register_workflow(self, workflow_def: WorkflowDef) -> bool:
        """Registers a workflow definition in the AMF registry for later lookup by ID."""
        return self._registry.register_workflow(workflow_def)

    def _get_skill_registry(self):
        """Get the skill registry instance."""
        return RegistryManager(base_dir=self.base_dir)
