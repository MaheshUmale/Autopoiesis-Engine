"""Local workflow executor — fallback when Temporal.io is unavailable.

Fixes:
- GAP-W1: No local workflow execution fallback
- GAP-W2: Workflow pause/resume capability
- N-1: EventEmitter integration for workflow events
- AC-2: Uses shared healing utility from PipelineExecutor
"""

import json
import time
import uuid
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.core.events import EventEmitter, Event, SystemEvents
from autopoiesis.amf.registry import AMFRegistry
from autopoiesis.amf.runtime import AMFRuntime, InvocationResult
from autopoiesis.amf.bus import AMFBusAdapter
from autopoiesis.amf.healing import AMFHealingAdapter
from autopoiesis.amf.schema import WorkflowDef, WorkflowNode, WorkflowEdge
from autopoiesis.mcp.pipeline import PipelineExecutor

logger = logging.getLogger("autopoiesis.workflows.local")


class LocalWorkflowExecutor:
    """Executes workflows locally without Temporal.io dependency.
    
    Features:
    - In-memory DAG execution with topological ordering
    - Checkpointing after each node for crash recovery
    - Resume from last completed node
    - Self-healing integration
    - Inter-agent message delivery
    """
    
    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.checkpoints_dir = self.base_dir / "workflow_checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

        self._registry = AMFRegistry(base_dir=base_dir)
        self._runtime = AMFRuntime(base_dir=base_dir)
        self._bus = AMFBusAdapter(base_dir=base_dir)
        self._healing = AMFHealingAdapter(base_dir=base_dir)
        # EventEmitter integration (N-1)
        self._events = EventEmitter(base_dir=base_dir)
    
    def execute_workflow(
        self,
        workflow_def: WorkflowDef,
        parameters: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
        resume_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a workflow locally.
        
        Args:
            workflow_def: Workflow definition
            parameters: Initial parameters
            execution_id: Optional execution ID for tracking
            resume_from: Optional checkpoint ID to resume from
            
        Returns:
            Dict with execution results
        """
        execution_id = execution_id or f"local_wf_{uuid.uuid4().hex[:12]}"
        parameters = parameters or workflow_def.parameters or {}

        # Emit workflow started event (N-1)
        self._events.emit(Event(
            event_type=SystemEvents.WORKFLOW_STARTED,
            source="LocalWorkflowExecutor",
            payload={
                "workflow_id": workflow_def.workflow_id,
                "execution_id": execution_id,
                "node_count": len(workflow_def.nodes),
            },
        ))
        
        # Load checkpoint if resuming
        node_outputs = {}
        completed_nodes = set()
        if resume_from:
            checkpoint = self._load_checkpoint(resume_from)
            if checkpoint:
                node_outputs = checkpoint.get("node_outputs", {})
                completed_nodes = set(checkpoint.get("completed_nodes", []))
                parameters = {**parameters, **checkpoint.get("parameters", {})}
        
        node_map = {node.node_id: node for node in workflow_def.nodes}
        errors = []
        
        # Build adjacency list for topological execution
        in_degree: Dict[str, int] = {node.node_id: 0 for node in workflow_def.nodes}
        adjacency: Dict[str, List[str]] = {node.node_id: [] for node in workflow_def.nodes}
        for edge in workflow_def.edges:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1
        
        # Build step mapping for template resolution
        step_map = {}
        for i, node in enumerate(workflow_def.nodes, 1):
            step_map[f"step_{i}"] = node.node_id
        
        # Execute nodes in topological order
        queue = [nid for nid in in_degree if in_degree[nid] == 0 and nid not in completed_nodes]
        start_time = time.time()
        
        while queue:
            current_id = queue.pop(0)
            if current_id not in node_map or current_id in completed_nodes:
                continue
            
            node = node_map[current_id]
            node_inputs = self._resolve_node_inputs(node, parameters, node_outputs, step_map)
            
            # Check for inter-agent messages before execution
            self._consume_agent_messages(node.agent_id, node_inputs)
            
            # Execute node
            result = self._runtime.invoke_capability(
                agent_id=node.agent_id,
                capability_name=node.capability,
                inputs=node_inputs,
            )
            
            if result.success:
                node_outputs[current_id] = result.output
                completed_nodes.add(current_id)

                # Emit node completed event (N-1)
                self._events.emit(Event(
                    event_type=SystemEvents.WORKFLOW_NODE_COMPLETED,
                    source="LocalWorkflowExecutor",
                    payload={
                        "workflow_id": workflow_def.workflow_id,
                        "node_id": current_id,
                        "agent_id": node.agent_id,
                        "capability": node.capability,
                    },
                ))
                
                # Deliver output to target agents via bus
                for edge in workflow_def.edges:
                    if edge.source == current_id:
                        self._bus.deliver_to_agent(
                            agent_id=node_map[edge.target].agent_id,
                            message=self._bus.broadcast(
                                channel=f"local.workflow.{workflow_def.workflow_id}.{edge.target}",
                                sender_agent=node.agent_id,
                                payload=result.output,
                                capability=node.capability,
                            ),
                        )
                
                # Save checkpoint after each successful node
                self._save_checkpoint(execution_id, workflow_def.workflow_id, {
                    "node_outputs": node_outputs,
                    "completed_nodes": list(completed_nodes),
                    "parameters": parameters,
                })
            else:
                # Attempt healing
                suggestion = self._healing.heal_capability_failure(
                    agent_id=node.agent_id,
                    capability=node.capability,
                    error_type=result.error_type or "LogicError",
                    error_msg=result.stderr,
                )
                
                # Retry with fix if available
                healed = False
                if suggestion.source == "cache" and suggestion.fix_code_patch:
                    # Apply fix and retry using shared utility (AC-2)
                    from autopoiesis.sandbox.executor import SandboxExecutor
                    from autopoiesis.registry.manager import RegistryManager
                    
                    reg = RegistryManager(base_dir=self.base_dir)
                    agent_def = self._registry.get_agent_def(node.agent_id)
                    if agent_def:
                        for cap in agent_def.capabilities:
                            if cap.name == node.capability:
                                skill = reg.get_skill(cap.skill_id)
                                if skill and skill.file_path:
                                    original_code = Path(skill.file_path).read_text(encoding="utf-8")
                                    # Use shared healing utility (AC-2)
                                    patched_code = PipelineExecutor.apply_fix_to_code(original_code, suggestion.fix_code_patch)
                                    
                                    enriched_inputs = dict(node_inputs)
                                    enriched_inputs["_agent_id"] = node.agent_id
                                    enriched_inputs["_capability"] = node.capability
                                    enriched_inputs["_cwd"] = str(Path.cwd())
                                    
                                    exec_res = SandboxExecutor.execute_skill_code(patched_code, enriched_inputs)
                                    if exec_res.success:
                                        node_outputs[current_id] = exec_res.output_payload
                                        completed_nodes.add(current_id)
                                        self._healing.record_healing_outcome(suggestion.pattern_id, True)
                                        
                                        # Emit healing applied event (N-1)
                                        self._events.emit(Event(
                                            event_type=SystemEvents.HEALING_APPLIED,
                                            source="LocalWorkflowExecutor",
                                            payload={
                                                "workflow_id": workflow_def.workflow_id,
                                                "node_id": current_id,
                                                "pattern_id": suggestion.pattern_id,
                                            },
                                        ))
                                        
                                        # Save checkpoint
                                        self._save_checkpoint(execution_id, workflow_def.workflow_id, {
                                            "node_outputs": node_outputs,
                                            "completed_nodes": list(completed_nodes),
                                            "parameters": parameters,
                                        })
                                        healed = True
                                        break
                                    else:
                                        self._healing.record_healing_outcome(suggestion.pattern_id, False)
                                        # Emit healing failed event (N-1)
                                        self._events.emit(Event(
                                            event_type=SystemEvents.HEALING_FAILED,
                                            source="LocalWorkflowExecutor",
                                            payload={
                                                "workflow_id": workflow_def.workflow_id,
                                                "node_id": current_id,
                                                "pattern_id": suggestion.pattern_id,
                                            },
                                        ))
                
                if not healed:
                    # Node failed
                    errors.append({
                        "node_id": current_id,
                        "agent_id": node.agent_id,
                        "capability": node.capability,
                        "error": result.stderr,
                        "error_type": result.error_type,
                    })
                    break
            
            # Add successors to queue
            for edge in workflow_def.edges:
                if edge.source == current_id:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)
        
        exec_time = time.time() - start_time
        
        # Emit workflow completed/failed event (N-1)
        if len(errors) == 0 and len(completed_nodes) == len(workflow_def.nodes):
            self._events.emit(Event(
                event_type=SystemEvents.WORKFLOW_COMPLETED,
                source="LocalWorkflowExecutor",
                payload={
                    "workflow_id": workflow_def.workflow_id,
                    "execution_id": execution_id,
                    "execution_time_sec": round(exec_time, 3),
                },
            ))
        else:
            self._events.emit(Event(
                event_type=SystemEvents.WORKFLOW_FAILED,
                source="LocalWorkflowExecutor",
                payload={
                    "workflow_id": workflow_def.workflow_id,
                    "execution_id": execution_id,
                    "errors": len(errors),
                },
            ))
        
        return {
            "execution_id": execution_id,
            "workflow_id": workflow_def.workflow_id,
            "success": len(errors) == 0 and len(completed_nodes) == len(workflow_def.nodes),
            "node_outputs": node_outputs,
            "completed_nodes": list(completed_nodes),
            "errors": errors,
            "execution_time_sec": round(exec_time, 3),
            "resumable": len(errors) > 0 and len(completed_nodes) < len(workflow_def.nodes),
        }
    
    def _resolve_node_inputs(
        self,
        node: WorkflowNode,
        parameters: Dict[str, Any],
        node_outputs: Dict[str, Any],
        step_map: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Resolve node inputs with parameter and step output injection."""
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
    
    def _consume_agent_messages(self, agent_id: str, inputs: Dict[str, Any]) -> None:
        """Consume pending messages for an agent and inject into inputs."""
        channel = f"amf.agent.{agent_id}"
        messages = self._bus.get_messages(channel=channel, limit=10, unread_only=True)
        if messages:
            inputs["_pending_messages"] = messages
            # Mark messages as read
            for msg in messages:
                self._bus.mark_read(msg.get("message_id", ""))
    
    def _save_checkpoint(
        self,
        execution_id: str,
        workflow_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Save workflow execution checkpoint."""
        checkpoint_file = self.checkpoints_dir / f"{execution_id}.json"
        checkpoint_data = {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            **data,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        tmp_file = checkpoint_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")
        tmp_file.replace(checkpoint_file)
    
    def _load_checkpoint(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Load workflow execution checkpoint."""
        checkpoint_file = self.checkpoints_dir / f"{execution_id}.json"
        if checkpoint_file.exists():
            try:
                return json.loads(checkpoint_file.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None
    
    def list_checkpoints(self, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available checkpoints, optionally filtered by workflow ID."""
        checkpoints = []
        for cp_file in self.checkpoints_dir.glob("*.json"):
            try:
                data = json.loads(cp_file.read_text(encoding="utf-8"))
                if workflow_id is None or data.get("workflow_id") == workflow_id:
                    checkpoints.append({
                        "execution_id": data.get("execution_id"),
                        "workflow_id": data.get("workflow_id"),
                        "completed_nodes": data.get("completed_nodes", []),
                        "saved_at": data.get("saved_at"),
                    })
            except Exception:
                continue
        return checkpoints
    
    def resume_workflow(
        self,
        execution_id: str,
        workflow_def: WorkflowDef,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resume a workflow from its last checkpoint.
        
        Fixes GAP-W2: Workflow pause/resume capability.
        """
        checkpoint = self._load_checkpoint(execution_id)
        if not checkpoint:
            raise ValueError(f"No checkpoint found for execution {execution_id}")
        
        merged_params = dict(workflow_def.parameters or {})
        if parameters:
            merged_params.update(parameters)
        
        return self.execute_workflow(
            workflow_def=workflow_def,
            parameters=merged_params,
            execution_id=execution_id,
            resume_from=execution_id,
        )
