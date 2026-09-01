"""AMF Runtime — capability invocation wrapper around SandboxExecutor."""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.sandbox.executor import SandboxExecutor
from autopoiesis.registry.manager import RegistryManager
from autopoiesis.amf.registry import AMFRegistry
from autopoiesis.amf.schema import AgentDef, Capability


class InvocationResult(BaseModel):
    """Standardized result from AMF capability invocation."""
    agent_id: str
    capability: str
    success: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    execution_time_sec: float = 0.0
    error_type: Optional[str] = None


class AMFRuntime:
    """Wraps SandboxExecutor with AMF capability routing and context injection.

    Injects agent context into every invocation:
    - _agent_id: the calling agent
    - _session_id: AMF session
    - _capability: invoked capability name
    - _memory: agent persistent memory
    """

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self._registry = AMFRegistry(base_dir=base_dir)
        self._session_mgr = None  # lazy init via AgentLifecycle when needed

    def _get_session_mgr(self):
        if self._session_mgr is None:
            from autopoiesis.core.session import AgentSessionManager
            self._session_mgr = AgentSessionManager(base_dir=self.base_dir)
        return self._session_mgr

    def _get_skill_registry(self) -> RegistryManager:
        return RegistryManager(base_dir=self.base_dir)

    def invoke_capability(
        self,
        agent_id: str,
        capability_name: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> InvocationResult:
        """Invokes a capability by name for a given agent.

        Args:
            agent_id: The agent invoking the capability
            capability_name: Name of the capability to invoke
            inputs: Input payload for the capability

        Returns:
            InvocationResult with success status and output
        """
        start_time = time.time()
        inputs = inputs or {}

        # Resolve agent and capability
        agent_def = self._registry.get_agent_def(agent_id)
        if not agent_def:
            return InvocationResult(
                agent_id=agent_id,
                capability=capability_name,
                success=False,
                stderr=f"Agent '{agent_id}' not found in AMF registry.",
                error_type="AgentNotFoundError",
                execution_time_sec=time.time() - start_time,
            )

        capability = None
        for cap in agent_def.capabilities:
            if cap.name == capability_name:
                capability = cap
                break

        if not capability:
            return InvocationResult(
                agent_id=agent_id,
                capability=capability_name,
                success=False,
                stderr=f"Capability '{capability_name}' not found for agent '{agent_id}'.",
                error_type="CapabilityNotFoundError",
                execution_time_sec=time.time() - start_time,
            )

        # Get skill code
        reg = self._get_skill_registry()
        skill = reg.get_skill(capability.skill_id)
        if not skill or not skill.file_path:
            return InvocationResult(
                agent_id=agent_id,
                capability=capability_name,
                success=False,
                stderr=f"Skill '{capability.skill_id}' not found in registry.",
                error_type="SkillNotFoundError",
                execution_time_sec=time.time() - start_time,
            )

        python_code = Path(skill.file_path).read_text(encoding="utf-8")

        # Inject AMF context into payload
        session_mgr = self._get_session_mgr()
        session_id = session_mgr.get_or_create_session(agent_id=agent_id, namespace=agent_def.namespace)
        session = session_mgr.get_session(session_id) or {}

        enriched_inputs = dict(inputs)
        enriched_inputs["_agent_id"] = agent_id
        enriched_inputs["_session_id"] = session_id
        enriched_inputs["_capability"] = capability_name
        enriched_inputs["_memory"] = session_mgr.get_all_memory(session_id)
        enriched_inputs["_cwd"] = str(Path.cwd())

        # Execute with dynamic timeout
        input_bytes = len(json.dumps(enriched_inputs).encode("utf-8"))
        timeout = SandboxExecutor.calculate_timeout(input_bytes)
        # Apply capability-specific timeout override
        effective_timeout = max(timeout, capability.timeout_sec)

        try:
            result = SandboxExecutor.execute_skill_code(
                python_code=python_code,
                input_payload=enriched_inputs,
            )
        except Exception as e:
            return InvocationResult(
                agent_id=agent_id,
                capability=capability_name,
                success=False,
                stderr=str(e),
                error_type="RuntimeError",
                execution_time_sec=time.time() - start_time,
            )

        exec_time = time.time() - start_time

        if not result.success:
            return InvocationResult(
                agent_id=agent_id,
                capability=capability_name,
                success=False,
                stdout=result.stdout,
                stderr=result.stderr,
                error_type=result.error_type,
                execution_time_sec=exec_time,
            )

        # Update session memory with capability output if requested
        memory_key = inputs.get("_memory_key")
        if memory_key and result.output_payload:
            session_mgr.set_memory(session_id, memory_key, result.output_payload)

        return InvocationResult(
            agent_id=agent_id,
            capability=capability_name,
            success=True,
            output=result.output_payload,
            stdout=result.stdout,
            stderr=result.stderr,
            execution_time_sec=exec_time,
        )

    def invoke_skill(
        self,
        skill_id: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> InvocationResult:
        """Direct skill invocation bypassing capability routing.

        Args:
            skill_id: Direct skill ID from registry
            inputs: Input payload
            context: Optional context dict with agent_id, session_id, etc.

        Returns:
            InvocationResult
        """
        start_time = time.time()
        context = context or {}
        inputs = dict(inputs)

        # Inject context
        agent_id = context.get("agent_id", "unknown")
        inputs["_agent_id"] = agent_id
        inputs["_session_id"] = context.get("session_id", "")
        inputs["_capability"] = context.get("capability", "direct_skill")
        inputs["_cwd"] = str(Path.cwd())

        reg = self._get_skill_registry()
        skill = reg.get_skill(skill_id)
        if not skill or not skill.file_path:
            return InvocationResult(
                agent_id=agent_id,
                capability="direct_skill",
                success=False,
                stderr=f"Skill '{skill_id}' not found.",
                error_type="SkillNotFoundError",
                execution_time_sec=time.time() - start_time,
            )

        python_code = Path(skill.file_path).read_text(encoding="utf-8")
        result = SandboxExecutor.execute_skill_code(python_code=python_code, input_payload=inputs)

        return InvocationResult(
            agent_id=agent_id,
            capability="direct_skill",
            success=result.success,
            output=result.output_payload,
            stdout=result.stdout,
            stderr=result.stderr,
            error_type=result.error_type,
            execution_time_sec=time.time() - start_time,
        )

    def health_check(self, agent_id: str) -> Dict[str, Any]:
        """Runs agent on_start hooks and returns health status."""
        agent_def = self._registry.get_agent_def(agent_id)
        if not agent_def:
            return {"agent_id": agent_id, "healthy": False, "error": "Agent not found"}

        status = {
            "agent_id": agent_id,
            "healthy": True,
            "dependencies": {},
            "on_start_hooks": [],
        }

        # Check dependencies
        dep_check = self._registry.resolve_dependencies(agent_id)
        status["dependencies_satisfied"] = dep_check["satisfied"]
        status["missing_dependencies"] = dep_check["missing"]
        status["dependency_warnings"] = dep_check["warnings"]
        if not dep_check["satisfied"]:
            status["healthy"] = False

        # Run on_start hooks
        for skill_id in agent_def.lifecycle_hooks.on_start:
            try:
                res = self.invoke_skill(skill_id, {"_health_check": True}, {"agent_id": agent_id})
                status["on_start_hooks"].append({
                    "skill_id": skill_id,
                    "success": res.success,
                    "error": res.stderr if not res.success else None,
                })
                if not res.success:
                    status["healthy"] = False
            except Exception as e:
                status["on_start_hooks"].append({
                    "skill_id": skill_id,
                    "success": False,
                    "error": str(e),
                })
                status["healthy"] = False

        return status
