import asyncio
import json
import re
import sqlite3
import time
import uuid
import datetime
from pathlib import Path
from typing import Any, Dict, List
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from sse_starlette.sse import EventSourceResponse

try:
    from mcp.server import MCPServer
except ImportError:
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as MCPServer
        except ImportError:
            from mcp.server import Server as MCPServer
import mcp.types as types

from autopoiesis.registry.manager import RegistryManager
from autopoiesis.sandbox.executor import SandboxExecutor
from autopoiesis.core.intent import LookAheadParser, ProjectConfig
from autopoiesis.core.session import AgentSessionManager
from autopoiesis.core.messaging import AgentMessageBus
from autopoiesis.core.observability import AgenticObservability
from autopoiesis.core.healing import HealLearningCache
from autopoiesis.storage.migrations import migrate_autopoiesis_db
from autopoiesis.cli.init import init_workspace, PlatformAdapter
from autopoiesis.mcp.dashboard import DASHBOARD_HTML
from autopoiesis.mcp.pipeline import PipelineExecutor, log_visual_activity, record_mcp_tool_trace, GREEN, CYAN, YELLOW, MAGENTA


def ensure_workspace_initialized(base_dir: str = ".autopoiesis"):
    """Automatically self-initializes the workspace if database or registry is missing."""
    import os
    db_file = os.path.join(base_dir, "autopoiesis.db")
    if not os.path.exists(db_file):
        log_visual_activity("AUTO-INIT", "Workspace not initialized. Auto-running self-initialization...", YELLOW)
        init_workspace(base_dir)
        log_visual_activity("AUTO-INIT", "Workspace & seed database initialized successfully!", GREEN)
    else:
        # Run startup delta indexing reconciliation
        migrate_autopoiesis_db(db_file)
        reg = RegistryManager(base_dir=base_dir)
        reg.sync_delta_indexing()


def create_mcp_server(base_dir: str = ".autopoiesis") -> MCPServer:
    """Creates and configures an MCP Server instance exposing Level 1 & Level 2 active micro-skills."""
    ensure_workspace_initialized(base_dir)

    app_server = MCPServer("autopoiesis-mcp-server")

    # Singleton agentic support infrastructure
    _session_mgr = AgentSessionManager(base_dir=base_dir)
    _msg_bus = AgentMessageBus(base_dir=base_dir)
    _observability = AgenticObservability(base_dir=base_dir)
    _heal_cache = HealLearningCache(base_dir=base_dir)

    # Shared pipeline executor (fixes GAP-L2: code duplication)
    _pipeline = PipelineExecutor(
        base_dir=base_dir,
        session_mgr=_session_mgr,
        observability=_observability,
        heal_cache=_heal_cache,
    )

    def get_registry():
        return RegistryManager(base_dir=base_dir)

    # Register primary project orchestrator tool: run_intent / execute_macro_intent
    # Uses shared pipeline executor (fixes GAP-L2)
    async def run_intent_handler(
        intent: str,
        active_namespaces: List[str] = None,
        agent_id: str = "default_agent",
        session_id: str = "",
    ) -> str:
        result = _pipeline.execute_pipeline(
            intent=intent,
            active_namespaces=active_namespaces,
            agent_id=agent_id,
            session_id=session_id,
            genesis_mode=False,
            auto_heal=True,  # fixes GAP-L3: healing cache integration
        )
        return json.dumps(result, indent=2)

    app_server.add_tool(
        fn=run_intent_handler,
        name="run_intent",
        description="Catch-all orchestration tool. Call this tool with raw user instructions to execute natural language tasks, scripts, and workflows automatically.",
    )

    app_server.add_tool(
        fn=run_intent_handler,
        name="execute_macro_intent",
        description="Primary project orchestrator tool for end-to-end intent processing and resolution.",
    )

    # --- Agentic Support Tools ---

    async def agent_session_create(agent_id: str, namespace: str = "global", tags: List[str] = None) -> str:
        session_id = _session_mgr.get_or_create_session(agent_id=agent_id, namespace=namespace, tags=tags or [])
        return json.dumps({"session_id": session_id, "agent_id": agent_id, "namespace": namespace})

    app_server.add_tool(
        fn=agent_session_create,
        name="agent_session_create",
        description="Creates or retrieves an agent session for persistent memory and context.",
    )

    async def agent_memory_set(session_id: str, key: str, value: Any) -> str:
        ok = _session_mgr.set_memory(session_id, key, value)
        return json.dumps({"status": "success" if ok else "error", "session_id": session_id, "key": key})

    app_server.add_tool(
        fn=agent_memory_set,
        name="agent_memory_set",
        description="Stores a key-value pair in an agent session's persistent memory.",
    )

    async def agent_memory_get(session_id: str, key: str, default: Any = None) -> str:
        value = _session_mgr.get_memory(session_id, key, default)
        return json.dumps({"session_id": session_id, "key": key, "value": value})

    app_server.add_tool(
        fn=agent_memory_get,
        name="agent_memory_get",
        description="Retrieves a value from an agent session's persistent memory.",
    )

    # --- Message Bus Tools (fixes GAP-L1: callback invocation) ---

    async def message_bus_publish(channel: str, sender: str, payload: Any, reply_to: str = "") -> str:
        msg_id = _msg_bus.publish(channel=channel, sender=sender, payload=payload, reply_to=reply_to or None)
        return json.dumps({"status": "published", "message_id": msg_id, "channel": channel})

    app_server.add_tool(
        fn=message_bus_publish,
        name="message_bus_publish",
        description="Publishes a message to an agent message bus channel.",
    )

    async def message_bus_subscribe(channel: str, agent_id: str) -> str:
        sub_id = _msg_bus.subscribe(channel=channel, agent_id=agent_id)
        return json.dumps({"status": "subscribed", "subscription_id": sub_id, "channel": channel, "agent_id": agent_id})

    app_server.add_tool(
        fn=message_bus_subscribe,
        name="message_bus_subscribe",
        description="Subscribes an agent to a message bus channel.",
    )

    # --- Observability Tools ---

    async def observability_metrics() -> str:
        metrics = {
            "total_executions": _observability.total_executions,
            "success_rate_pct": _observability.success_rate,
            "avg_execution_time_sec": _observability.avg_execution_time,
            "avg_execution_time_success_sec": _observability.avg_execution_time_success,
            "avg_execution_time_failure_sec": _observability.avg_execution_time_failure,
            "error_type_distribution": _observability.error_type_distribution,
            "top_slow_skills": _observability.get_top_slow_skills(5),
            "error_summary": _observability.get_error_summary(),
        }
        return json.dumps(metrics, indent=2)

    app_server.add_tool(
        fn=observability_metrics,
        name="observability_metrics",
        description="Returns aggregated observability metrics: success rates, error distribution, and top slow skills.",
    )

    # --- Healing Tools ---

    async def heal_suggestion(skill_id: str, error_type: str, error_msg: str) -> str:
        suggestion = _heal_cache.find_suggested_fix(skill_id=skill_id, error_type=error_type, error_msg=error_msg)
        if suggestion:
            return json.dumps({
                "status": "suggestion_found",
                "pattern_id": suggestion.pattern_id,
                "fix_description": suggestion.fix_description,
                "fix_code_patch": suggestion.fix_code_patch,
                "success_rate": suggestion.success_count / (suggestion.success_count + suggestion.failure_count) if (suggestion.success_count + suggestion.failure_count) > 0 else 0.0,
            })
        return json.dumps({"status": "no_suggestion", "message": "No learned fix found for this error pattern."})

    app_server.add_tool(
        fn=heal_suggestion,
        name="heal_suggestion",
        description="Suggests a learned fix for a skill error based on past healing patterns.",
    )

    # --- Auto-Synthesis Tools (uses shared pipeline) ---

    async def synthesize_skill(step_description: str, namespace: str = "global", test_inputs: Dict[str, Any] = None) -> str:
        """Explicitly synthesize and register a new micro-skill from a natural language description.
        
        Returns skill_id, generated_code, test_result, and status.
        """
        reg = get_registry()
        parser = LookAheadParser(reg)
        
        try:
            skill_meta = parser.synthesize_and_register_skill(
                step_description=step_description,
                namespace=namespace,
                root_registry_dir=Path(base_dir) / "registry",
            )
            
            result = {
                "status": "success",
                "skill_id": skill_meta.id,
                "namespace": skill_meta.namespace,
                "scope_level": skill_meta.scope_level,
                "description": skill_meta.description,
                "file_path": skill_meta.file_path,
                "synthesized": True,
            }
            
            if test_inputs:
                skill = reg.get_skill(skill_meta.id)
                if skill and skill.file_path:
                    python_code = open(skill.file_path, "r", encoding="utf-8").read()
                    exec_res = SandboxExecutor.execute_skill_code(python_code, test_inputs)
                    result["test_result"] = {
                        "success": exec_res.success,
                        "output": exec_res.output_payload,
                        "stdout": exec_res.stdout,
                        "stderr": exec_res.stderr,
                        "execution_time_sec": exec_res.execution_time_sec,
                        "error_type": exec_res.error_type,
                    }
            
            log_visual_activity("SYNTHESIS", f"Created skill '{skill_meta.id}' from: '{step_description}'", GREEN)
            return json.dumps(result, indent=2)
            
        except Exception as e:
            log_visual_activity("SYNTHESIS ERROR", f"Failed to synthesize skill: {e}", YELLOW)
            return json.dumps({"status": "error", "error": str(e), "step_description": step_description})

    app_server.add_tool(
        fn=synthesize_skill,
        name="synthesize_skill",
        description="Explicitly synthesize and register a new micro-skill from a natural language description. Returns skill metadata and optional test results.",
    )

    async def synthesize_and_run(intent: str, active_namespaces: List[str] = None) -> str:
        """Synthesize missing skills and execute the full intent pipeline.
        
        Uses shared pipeline executor (fixes GAP-L2).
        """
        result = _pipeline.execute_pipeline(
            intent=intent,
            active_namespaces=active_namespaces,
            genesis_mode=False,
            auto_heal=True,
        )
        return json.dumps(result, indent=2)

    app_server.add_tool(
        fn=synthesize_and_run,
        name="synthesize_and_run",
        description="Explicitly synthesize missing skills and execute the full intent pipeline. Returns execution log with synthesis statistics.",
    )

    # --- Genesis Tools (Level 0) ---

    async def amf_genesis_forge_skill(specification: Dict[str, Any], namespace: str = "global") -> str:
        """Forge a new micro-skill from first-principles structured specification (Level 0 Genesis).
        
        Args:
            specification: Structured SkillSpecification with description, inputs, outputs, behavior.
            namespace: Target namespace for the forged skill.
        """
        reg = get_registry()
        parser = LookAheadParser(reg)
        try:
            skill_meta = parser.genesis_synthesize(
                step_description=specification.get("description", "forged skill"),
                namespace=namespace,
                root_registry_dir=Path(base_dir) / "registry",
            )
            result = {
                "status": "success",
                "skill_id": skill_meta.id,
                "namespace": skill_meta.namespace,
                "scope_level": skill_meta.scope_level,
                "description": skill_meta.description,
                "file_path": skill_meta.file_path,
                "genesis": True,
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e), "genesis": True})

    app_server.add_tool(
        fn=amf_genesis_forge_skill,
        name="amf_genesis_forge_skill",
        description="Forge a new micro-skill from a structured SkillSpecification. Level 0 Genesis pathway for novel skill creation.",
    )

    async def amf_genesis_synthesize(intent: str, active_namespaces: List[str] = None) -> str:
        """Synthesize missing skills using Level 0 Genesis pathway and execute the full intent pipeline.
        
        Uses shared pipeline executor (fixes GAP-L2).
        """
        result = _pipeline.execute_pipeline(
            intent=intent,
            active_namespaces=active_namespaces,
            genesis_mode=True,
            auto_heal=True,
        )
        return json.dumps(result, indent=2)

    app_server.add_tool(
        fn=amf_genesis_synthesize,
        name="amf_genesis_synthesize",
        description="Synthesize missing skills using Level 0 Genesis pathway and execute the full intent pipeline. Creates novel skills without registry overlap.",
    )

    # --- AI Agent Skill Submission Tool ---

    async def submit_ai_skill(
        skill_id: str,
        namespace: str,
        description: str,
        python_code: str,
        inputs: Dict[str, Any] = None,
        outputs: Dict[str, Any] = None,
        test_inputs: Dict[str, Any] = None,
    ) -> str:
        """Submit AI-generated skill code for registration.

        This tool allows AI agents to register custom-generated skills
        when the system identifies a complex pattern that requires
        human-level code generation.

        Args:
            skill_id: Unique identifier for the skill (e.g., 'global.custom_skill')
            namespace: Target namespace for the skill
            description: Human-readable description of the skill
            python_code: Python code with a main(inputs: dict) -> dict function
            inputs: JSON Schema for inputs
            outputs: JSON Schema for outputs
            test_inputs: Optional test inputs to verify the skill

        Returns:
            JSON with status, skill_id, test_result, and file_path
        """
        reg = get_registry()

        # Verify the code works in sandbox
        verification_payload = test_inputs if test_inputs else {"payload": "ai_skill_verification"}
        exec_res = SandboxExecutor.execute_skill_code(python_code, verification_payload)

        if not exec_res.success:
            log_visual_activity(
                "AI SKILL REJECTED",
                f"Skill '{skill_id}' failed verification: {exec_res.stderr}",
                YELLOW,
            )
            return json.dumps({
                "status": "verification_failed",
                "skill_id": skill_id,
                "error": exec_res.stderr,
                "error_type": exec_res.error_type,
            })

        # Register the verified skill
        try:
            skill_meta = reg.register_skill(
                skill_id=skill_id,
                namespace=namespace,
                scope_level="ai_generated",
                description=description,
                inputs=inputs or {"type": "object", "properties": {"payload": {}}},
                outputs=outputs or {"type": "object", "properties": {"status": {"type": "string"}, "output": {}}},
                python_code=python_code,
                root_registry_dir=Path(base_dir) / "registry",
            )

            log_visual_activity(
                "AI SKILL REGISTERED",
                f"Skill '{skill_id}' verified and registered successfully",
                GREEN,
            )

            return json.dumps({
                "status": "success",
                "skill_id": skill_meta.id,
                "namespace": skill_meta.namespace,
                "scope_level": skill_meta.scope_level,
                "file_path": skill_meta.file_path,
                "test_result": {
                    "success": exec_res.success,
                    "output": exec_res.output_payload,
                    "execution_time_sec": exec_res.execution_time_sec,
                },
                "ai_generated": True,
            }, indent=2)

        except Exception as e:
            log_visual_activity(
                "AI SKILL ERROR",
                f"Failed to register skill '{skill_id}': {e}",
                YELLOW,
            )
            return json.dumps({
                "status": "error",
                "skill_id": skill_id,
                "error": str(e),
            })

    app_server.add_tool(
        fn=submit_ai_skill,
        name="submit_ai_skill",
        description="Submit AI-generated skill code for registration. Use when synthesis_required=True and you have generated custom Python code.",
    )

    # --- Retry Pipeline Tool ---

    async def retry_intent(
        intent: str,
        active_namespaces: List[str] = None,
        agent_id: str = "default_agent",
        session_id: str = "",
    ) -> str:
        """Retry pipeline execution after AI skills have been submitted.

        Call this after submitting AI-generated skills with submit_ai_skill()
        to re-run the pipeline with the newly registered skills.
        """
        result = _pipeline.retry_with_ai_skills(
            intent=intent,
            active_namespaces=active_namespaces,
            agent_id=agent_id,
            session_id=session_id,
            auto_heal=True,
        )
        return json.dumps(result, indent=2)

    app_server.add_tool(
        fn=retry_intent,
        name="retry_intent",
        description="Retry pipeline execution after AI skills have been submitted. Call submit_ai_skill() first, then retry.",
    )

    # --- AMF Tools ---

    async def amf_register_agent(manifest_path: str) -> str:
        from autopoiesis.amf.registry import AMFRegistry
        amf_reg = AMFRegistry(base_dir=base_dir)
        path = PlatformAdapter.sanitize_path(manifest_path)
        if not path.exists():
            return json.dumps({"status": "error", "error": f"Manifest not found: {manifest_path}"})
        try:
            records = amf_reg.register_manifest(path)
            return json.dumps({"status": "success", "registered_count": len(records), "agents": [r.agent_id for r in records]})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    app_server.add_tool(
        fn=amf_register_agent,
        name="amf_register_agent",
        description="Registers AMF agents from a manifest JSON/YAML file.",
    )

    async def amf_start_agent(agent_id: str) -> str:
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        try:
            state = lifecycle.start_agent(agent_id)
            return json.dumps({"status": "success", "agent_id": agent_id, "state": state.state})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    app_server.add_tool(
        fn=amf_start_agent,
        name="amf_start_agent",
        description="Starts a registered AMF agent (runs on_start hooks).",
    )

    async def amf_stop_agent(agent_id: str) -> str:
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        try:
            state = lifecycle.stop_agent(agent_id)
            return json.dumps({"status": "success", "agent_id": agent_id, "state": state.state})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    app_server.add_tool(
        fn=amf_stop_agent,
        name="amf_stop_agent",
        description="Stops a running AMF agent (runs on_stop hooks).",
    )

    async def amf_invoke_capability(agent_id: str, capability: str, inputs: Dict[str, Any] = None) -> str:
        from autopoiesis.amf.runtime import AMFRuntime
        runtime = AMFRuntime(base_dir=base_dir)
        result = runtime.invoke_capability(agent_id, capability, inputs or {})
        if result.success:
            return json.dumps({"status": "success", "output": result.output, "execution_time_sec": result.execution_time_sec})
        return json.dumps({"status": "error", "error": result.stderr, "error_type": result.error_type})

    app_server.add_tool(
        fn=amf_invoke_capability,
        name="amf_invoke_capability",
        description="Invokes a capability on an AMF agent by name.",
    )

    async def amf_workflow_run(workflow_id: str, parameters: Dict[str, Any] = None) -> str:
        from autopoiesis.amf.orchestrator import AMFOrchestrator
        orchestrator = AMFOrchestrator(base_dir=base_dir)
        try:
            result = orchestrator.run_workflow_by_id(workflow_id, parameters=parameters)
            return json.dumps(result.model_dump(), indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    app_server.add_tool(
        fn=amf_workflow_run,
        name="amf_workflow_run",
        description="Runs a registered AMF workflow by ID.",
    )

    async def amf_workflow_register(workflow_json: Dict[str, Any]) -> str:
        from autopoiesis.amf.orchestrator import AMFOrchestrator
        from autopoiesis.amf.schema import WorkflowDef
        orchestrator = AMFOrchestrator(base_dir=base_dir)
        try:
            wf_def = WorkflowDef(**workflow_json)
            ok = orchestrator.register_workflow(wf_def)
            if ok:
                return json.dumps({"status": "success", "workflow_id": wf_def.workflow_id})
            return json.dumps({"status": "error", "error": "Failed to register workflow"})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    app_server.add_tool(
        fn=amf_workflow_register,
        name="amf_workflow_register",
        description="Registers a workflow definition in the AMF registry.",
    )

    # fixes GAP-I1: Expose missing AMF tools via MCP
    async def amf_workflow_list(namespace: str = None) -> str:
        from autopoiesis.amf.registry import AMFRegistry
        reg = AMFRegistry(base_dir=base_dir)
        workflows = reg.list_workflows(namespace=namespace)
        return json.dumps({
            "status": "success",
            "workflows": [w.model_dump() for w in workflows],
        })

    app_server.add_tool(
        fn=amf_workflow_list,
        name="amf_workflow_list",
        description="Lists all registered AMF workflows, optionally filtered by namespace.",
    )

    async def amf_list_agents(namespace: str = None, state: str = None) -> str:
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        agents = lifecycle.list_agents(namespace=namespace, state=state)
        return json.dumps({"status": "success", "agents": agents})

    app_server.add_tool(
        fn=amf_list_agents,
        name="amf_list_agents",
        description="Lists all registered AMF agents and their status.",
    )

    async def amf_get_agent_status(agent_id: str) -> str:
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        status = lifecycle.get_agent_status(agent_id)
        if status:
            return json.dumps({"status": "success", "agent": status})
        return json.dumps({"status": "error", "error": f"Agent '{agent_id}' not found."})

    app_server.add_tool(
        fn=amf_get_agent_status,
        name="amf_get_agent_status",
        description="Gets detailed status of an AMF agent.",
    )

    async def amf_pause_agent(agent_id: str) -> str:
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        try:
            state = lifecycle.pause_agent(agent_id)
            return json.dumps({"status": "success", "agent_id": agent_id, "state": state.state})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    app_server.add_tool(
        fn=amf_pause_agent,
        name="amf_pause_agent",
        description="Pauses a running AMF agent.",
    )

    async def amf_resume_agent(agent_id: str) -> str:
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        try:
            state = lifecycle.resume_agent(agent_id)
            return json.dumps({"status": "success", "agent_id": agent_id, "state": state.state})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    app_server.add_tool(
        fn=amf_resume_agent,
        name="amf_resume_agent",
        description="Resumes a paused AMF agent.",
    )

    async def amf_destroy_agent(agent_id: str) -> str:
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        ok = lifecycle.destroy_agent(agent_id)
        if ok:
            return json.dumps({"status": "success", "agent_id": agent_id})
        return json.dumps({"status": "error", "error": f"Agent '{agent_id}' not found."})

    app_server.add_tool(
        fn=amf_destroy_agent,
        name="amf_destroy_agent",
        description="Destroys an AMF agent and removes its state.",
    )

    async def amf_inspect(agent_id: str) -> str:
        from autopoiesis.amf.lifecycle import AgentLifecycle
        from autopoiesis.amf.metrics import AMFMetricsAdapter
        from autopoiesis.amf.healing import AMFHealingAdapter
        lifecycle = AgentLifecycle(base_dir=base_dir)
        status = lifecycle.get_agent_status(agent_id)
        if not status:
            return json.dumps({"status": "error", "error": f"Agent '{agent_id}' not found."})
        metrics = AMFMetricsAdapter(base_dir=base_dir)
        healing = AMFHealingAdapter(base_dir=base_dir)
        health = metrics.get_agent_health(agent_id)
        patterns = healing.get_patterns_for_agent(agent_id)
        result = {
            "status": "success",
            "agent": status,
            "health": health.model_dump(),
            "healing_patterns": [p.model_dump() for p in patterns[:5]],
        }
        return json.dumps(result, indent=2)

    app_server.add_tool(
        fn=amf_inspect,
        name="amf_inspect",
        description="Shows detailed agent definition, status, health metrics, and learned healing patterns.",
    )

    async def amf_logs(agent_id: str, limit: int = 20) -> str:
        from autopoiesis.core.session import AgentSessionManager
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        status = lifecycle.get_agent_status(agent_id)
        if not status or not status.get("session_id"):
            return json.dumps({"status": "error", "error": f"Agent '{agent_id}' not found or has no session."})
        session_mgr = AgentSessionManager(base_dir=base_dir)
        history = session_mgr.get_recent_history(status["session_id"], limit=limit)
        return json.dumps({"status": "success", "agent_id": agent_id, "logs": history})

    app_server.add_tool(
        fn=amf_logs,
        name="amf_logs",
        description="Shows recent execution logs for an AMF agent.",
    )

    async def amf_agent_health(agent_id: str) -> str:
        from autopoiesis.amf.runtime import AMFRuntime
        runtime = AMFRuntime(base_dir=base_dir)
        health = runtime.health_check(agent_id)
        return json.dumps(health, indent=2)

    app_server.add_tool(
        fn=amf_agent_health,
        name="amf_agent_health",
        description="Runs health check on an AMF agent and returns health status.",
    )

    async def amf_heal_agent(agent_id: str, capability: str, error_type: str, error_msg: str) -> str:
        from autopoiesis.amf.healing import AMFHealingAdapter
        healing = AMFHealingAdapter(base_dir=base_dir)
        suggestion = healing.heal_capability_failure(
            agent_id=agent_id,
            capability=capability,
            error_type=error_type,
            error_msg=error_msg,
        )
        return json.dumps(suggestion.model_dump(), indent=2)

    app_server.add_tool(
        fn=amf_heal_agent,
        name="amf_heal_agent",
        description="Gets healing suggestion for a failed capability on an AMF agent.",
    )

    # --- Register individual skills as MCP tools ---

    registry = get_registry()
    with sqlite3.connect(registry.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, description, inputs_json FROM skills")
        rows = cursor.fetchall()
        for row in rows:
            skill_id, desc, inputs_json = row[0], row[1], row[2]

            def make_handler(s_id: str):
                async def skill_handler(**kwargs) -> str:
                    log_visual_activity("TOOL CALL EXECUTED", f"AI Agent invoked tool: '{s_id}'", CYAN)
                    reg = get_registry()
                    skill = reg.get_skill(s_id)
                    if not skill or not skill.file_path:
                        err_out = {"isError": True, "error": f"Skill '{s_id}' not found."}
                        record_mcp_tool_trace(base_dir, s_id, False, err_out, stderr="Skill not found")
                        return json.dumps(err_out)
                    python_code = open(skill.file_path, "r", encoding="utf-8").read()

                    log_visual_activity("SANDBOX RUN", f"Executing '{s_id}' in isolated sandbox...", YELLOW)
                    res = SandboxExecutor.execute_skill_code(python_code, kwargs)

                    record_mcp_tool_trace(
                        base_dir=base_dir,
                        skill_id=s_id,
                        success=res.success,
                        output=res.output_payload,
                        stdout=res.stdout,
                        stderr=res.stderr,
                        execution_time_sec=res.execution_time_sec,
                        error_type=res.error_type
                    )

                    if not res.success:
                        log_visual_activity("SANDBOX ERROR", f"Skill '{s_id}' failed: {res.stderr}", YELLOW)
                        return json.dumps({"isError": True, "error_type": res.error_type, "stderr": res.stderr})

                    log_visual_activity("SANDBOX SUCCESS", f"Skill '{s_id}' completed successfully in {res.execution_time_sec:.3f}s", GREEN)
                    return json.dumps(res.output_payload, indent=2)
                return skill_handler

            app_server.add_tool(
                fn=make_handler(skill_id),
                name=skill_id,
                description=desc or f"Skill {skill_id}",
            )

    return app_server


async def run_mcp_stdio_server():
    """Runs the MCP server over stdio transport."""
    ensure_workspace_initialized()
    log_visual_activity("DAEMON ACTIVE", "Autopoiesis Engine Daemon running in STDIO mode.", "\033[1m" + GREEN)
    server = create_mcp_server()
    await server.run_stdio_async()


def create_fastapi_app(base_dir: str = ".autopoiesis") -> FastAPI:
    """Creates FastAPI app for HTTP and SSE transport mode with Global Agent Dashboard UI."""
    ensure_workspace_initialized(base_dir)

    # Singleton agentic support infrastructure (accessible to route handlers via closure)
    _session_mgr = AgentSessionManager(base_dir=base_dir)
    _msg_bus = AgentMessageBus(base_dir=base_dir)
    _observability = AgenticObservability(base_dir=base_dir)
    _heal_cache = HealLearningCache(base_dir=base_dir)

    app = FastAPI(title="Autopoiesis Engine MCP Daemon")

    @app.get("/")
    @app.get("/ui")
    @app.get("/dashboard")
    async def dashboard_ui():
        """Serves the interactive Global Agent Dashboard UI."""
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/api/dashboard/agents")
    async def api_dashboard_agents():
        """API endpoint supplying agent stats and individual skill data for the dashboard."""
        registry = RegistryManager(base_dir=base_dir)
        agents = []
        core_count = 0
        variant_count = 0
        template_count = 0

        traces_dir = PlatformAdapter.sanitize_path(base_dir) / "traces"
        execution_runs = len(list(traces_dir.glob("*.json"))) if traces_dir.exists() else 0

        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, namespace, scope_level, description, file_path, ast_hash FROM skills")
            rows = cursor.fetchall()
            for r in rows:
                scope = r[2]
                if scope == "core":
                    core_count += 1
                elif scope == "variant":
                    variant_count += 1
                else:
                    template_count += 1

                agents.append({
                    "id": r[0],
                    "namespace": r[1],
                    "scope_level": r[2],
                    "description": r[3],
                    "file_path": r[4],
                    "ast_hash": r[5],
                })

        return JSONResponse(content={
            "agents": agents,
            "stats": {
                "core_count": core_count,
                "variant_count": variant_count,
                "template_count": template_count,
                "total_agents": len(agents),
                "execution_runs": execution_runs,
            }
        })

    @app.get("/api/dashboard/observability")
    async def api_dashboard_observability():
        """API endpoint for observability metrics."""
        return JSONResponse(content={
            "total_executions": _observability.total_executions,
            "success_rate_pct": _observability.success_rate,
            "avg_execution_time_sec": _observability.avg_execution_time,
            "error_type_distribution": _observability.error_type_distribution,
            "top_slow_skills": _observability.get_top_slow_skills(10),
            "error_summary": _observability.get_error_summary(),
        })

    @app.get("/api/dashboard/sessions")
    async def api_dashboard_sessions():
        """API endpoint for active agent sessions."""
        sessions = []
        for sid, data in _session_mgr._active.items():
            sessions.append({
                "session_id": sid,
                "agent_id": data.get("metadata", {}).get("agent_id"),
                "namespace": data.get("metadata", {}).get("namespace"),
                "total_invocations": data.get("metadata", {}).get("total_invocations", 0),
                "last_active_at": data.get("metadata", {}).get("last_active_at"),
            })
        return JSONResponse(content={"sessions": sessions})

    @app.get("/api/dashboard/messages")
    async def api_dashboard_messages():
        """API endpoint for message bus channels and stats."""
        return JSONResponse(content={
            "channels": _msg_bus.list_channels(),
            "channel_stats": _msg_bus.get_channel_stats(),
        })

    @app.get("/api/amf/agents")
    async def api_amf_agents():
        """API endpoint for AMF agents."""
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        agents = lifecycle.list_agents()
        return JSONResponse(content={"agents": agents})

    @app.get("/api/amf/workflows")
    async def api_amf_workflows():
        """API endpoint for AMF workflows."""
        from autopoiesis.amf.registry import AMFRegistry
        reg = AMFRegistry(base_dir=base_dir)
        workflows = reg.list_workflows()
        return JSONResponse(content={"workflows": [w.model_dump() for w in workflows]})

    @app.post("/api/amf/agents/{agent_id}/start")
    async def api_amf_start_agent(agent_id: str):
        """API endpoint to start an AMF agent."""
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        try:
            state = lifecycle.start_agent(agent_id)
            return JSONResponse(content={"status": "success", "agent_id": agent_id, "state": state.state})
        except Exception as e:
            return JSONResponse(content={"status": "error", "error": str(e)}, status_code=400)

    @app.post("/api/amf/agents/{agent_id}/stop")
    async def api_amf_stop_agent(agent_id: str):
        """API endpoint to stop an AMF agent."""
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        try:
            state = lifecycle.stop_agent(agent_id)
            return JSONResponse(content={"status": "success", "agent_id": agent_id, "state": state.state})
        except Exception as e:
            return JSONResponse(content={"status": "error", "error": str(e)}, status_code=400)

    @app.get("/api/amf/agents/{agent_id}/status")
    async def api_amf_agent_status(agent_id: str):
        """API endpoint to get AMF agent status."""
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        status = lifecycle.get_agent_status(agent_id)
        if status:
            return JSONResponse(content={"status": "success", "agent": status})
        return JSONResponse(content={"status": "error", "error": f"Agent '{agent_id}' not found."}, status_code=404)

    @app.get("/api/amf/agents/{agent_id}/logs")
    async def api_amf_agent_logs(agent_id: str, limit: int = 20):
        """API endpoint to get AMF agent logs."""
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        status = lifecycle.get_agent_status(agent_id)
        if not status or not status.get("session_id"):
            return JSONResponse(content={"status": "error", "error": f"Agent '{agent_id}' not found or has no session."}, status_code=404)
        history = _session_mgr.get_recent_history(status["session_id"], limit=limit)
        return JSONResponse(content={"status": "success", "agent_id": agent_id, "logs": history})

    @app.post("/api/amf/workflows/{workflow_id}/run")
    async def api_amf_run_workflow(workflow_id: str, parameters: Dict[str, Any] = None):
        """API endpoint to run an AMF workflow."""
        from autopoiesis.amf.orchestrator import AMFOrchestrator
        orchestrator = AMFOrchestrator(base_dir=base_dir)
        try:
            result = orchestrator.run_workflow_by_id(workflow_id, parameters=parameters or {})
            return JSONResponse(content=result.model_dump())
        except Exception as e:
            return JSONResponse(content={"status": "error", "error": str(e)}, status_code=400)

    @app.post("/api/intent/run")
    async def api_run_intent(request: Request):
        """API endpoint to run an intent pipeline."""
        body = await request.json()
        intent = body.get("intent", "")
        active_namespaces = body.get("active_namespaces", ["global"])
        agent_id = body.get("agent_id", "default_agent")

        # Use shared pipeline executor (fixes N-4: avoid creating new instances per request)
        result = _pipeline.execute_pipeline(
            intent=intent,
            active_namespaces=active_namespaces,
            agent_id=agent_id,
        )
        return JSONResponse(content=result)

    @app.get("/sse")
    async def sse_endpoint():
        """SSE endpoint for real-time updates."""
        async def event_generator():
            while True:
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "active_sessions": len(_session_mgr._active),
                        "total_executions": _observability.total_executions,
                    }),
                }
                await asyncio.sleep(5)

        return EventSourceResponse(event_generator())

    # --- Additional MCP-compatible endpoints ---

    @app.get("/tools")
    async def api_list_tools():
        """List all available tools (MCP-compatible endpoint)."""
        registry = RegistryManager(base_dir=base_dir)
        tools = []
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, description FROM skills")
            for row in cursor.fetchall():
                tools.append({
                    "name": row[0],
                    "description": row[1] or f"Skill {row[0]}",
                })
        return JSONResponse(content=tools)

    @app.get("/api/dashboard/logs/{skill_id:path}")
    async def api_dashboard_logs(skill_id: str):
        """Get logs for a specific skill/agent."""
        traces_dir = PlatformAdapter.sanitize_path(base_dir) / "traces"
        logs = []
        if traces_dir.exists():
            for trace_file in traces_dir.glob("*.json"):
                try:
                    data = json.loads(trace_file.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        for entry in data:
                            if entry.get("skill_id") == skill_id:
                                logs.append(entry)
                except Exception:
                    continue
        return JSONResponse(content={"agent_id": skill_id, "logs": logs[-50:]})

    @app.get("/resources/registry")
    async def api_resource_registry():
        """MCP resource endpoint for registry."""
        registry = RegistryManager(base_dir=base_dir)
        skills = []
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, namespace, scope_level, description FROM skills")
            for row in cursor.fetchall():
                skills.append({
                    "id": row[0],
                    "namespace": row[1],
                    "scope_level": row[2],
                    "description": row[3],
                })
        return JSONResponse(content={
            "resource": "resource://autopoiesis/registry",
            "skills": skills,
        })

    @app.get("/resources/config")
    async def api_resource_config():
        """MCP resource endpoint for config."""
        return JSONResponse(content={
            "resource": "resource://autopoiesis/config",
            "config": {
                "base_dir": str(base_dir),
                "version": "2.0.0",
            },
        })

    @app.post("/messages")
    async def api_messages(request: Request):
        """MCP JSON-RPC messages endpoint."""
        body = await request.json()
        method = body.get("method", "")
        params = body.get("params", {})
        
        if method == "tools/list":
            skill_registry = RegistryManager(base_dir=base_dir)
            tools = []
            with sqlite3.connect(skill_registry.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, description FROM skills")
                for row in cursor.fetchall():
                    tools.append({
                        "name": row[0],
                        "description": row[1] or f"Skill {row[0]}",
                    })
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"tools": tools},
            })
        
        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            
            # Handle genesis forge skill
            if tool_name == "amf_genesis_forge_skill":
                from autopoiesis.core.intent import LookAheadParser
                reg = RegistryManager(base_dir=base_dir)
                parser = LookAheadParser(reg)
                spec = arguments.get("specification", {})
                namespace = arguments.get("namespace", "global")
                skill_meta = parser.genesis_synthesize(
                    step_description=spec.get("description", "forged skill"),
                    namespace=namespace,
                    root_registry_dir=Path(base_dir) / "registry",
                )
                result = {
                    "status": "success",
                    "skill_id": skill_meta.id,
                    "namespace": skill_meta.namespace,
                    "scope_level": skill_meta.scope_level,
                    "description": skill_meta.description,
                    "file_path": skill_meta.file_path,
                    "genesis": True,
                }
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
                })
            
            # Handle genesis synthesize
            if tool_name == "amf_genesis_synthesize":
                from autopoiesis.mcp.pipeline import PipelineExecutor
                pipeline = PipelineExecutor(base_dir=base_dir)
                result = pipeline.execute_pipeline(
                    intent=arguments.get("intent", ""),
                    active_namespaces=arguments.get("active_namespaces", ["global"]),
                    genesis_mode=True,
                )
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
                })
            
            # Handle run_intent
            if tool_name == "run_intent":
                from autopoiesis.mcp.pipeline import PipelineExecutor
                pipeline = PipelineExecutor(base_dir=base_dir)
                result = pipeline.execute_pipeline(
                    intent=arguments.get("intent", ""),
                    active_namespaces=arguments.get("active_namespaces", ["global"]),
                )
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
                })
        
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })

    # --- REST API endpoints for MCP tools (for testing and direct access) ---

    @app.post("/tools/agent_session_create/execute")
    async def api_agent_session_create(request: Request):
        """REST endpoint for agent_session_create tool."""
        body = await request.json()
        session_id = _session_mgr.get_or_create_session(
            agent_id=body.get("agent_id"),
            namespace=body.get("namespace", "global"),
            tags=body.get("tags"),
        )
        return JSONResponse(content={"status": "success", "session_id": session_id, "agent_id": body.get("agent_id"), "namespace": body.get("namespace", "global")})

    @app.post("/tools/agent_memory_set/execute")
    async def api_agent_memory_set(request: Request):
        """REST endpoint for agent_memory_set tool."""
        body = await request.json()
        ok = _session_mgr.set_memory(body.get("session_id"), body.get("key"), body.get("value"))
        return JSONResponse(content={"status": "success" if ok else "error", "session_id": body.get("session_id"), "key": body.get("key")})

    @app.post("/tools/agent_memory_get/execute")
    async def api_agent_memory_get(request: Request):
        """REST endpoint for agent_memory_get tool."""
        body = await request.json()
        value = _session_mgr.get_memory(body.get("session_id"), body.get("key"), body.get("default"))
        return JSONResponse(content={"session_id": body.get("session_id"), "key": body.get("key"), "value": value})

    @app.post("/tools/message_bus_publish/execute")
    async def api_message_bus_publish(request: Request):
        """REST endpoint for message_bus_publish tool."""
        body = await request.json()
        msg_id = _msg_bus.publish(
            channel=body.get("channel"),
            sender=body.get("sender"),
            payload=body.get("payload"),
            reply_to=body.get("reply_to"),
        )
        return JSONResponse(content={"status": "published", "message_id": msg_id, "channel": body.get("channel")})

    @app.post("/tools/message_bus_subscribe/execute")
    async def api_message_bus_subscribe(request: Request):
        """REST endpoint for message_bus_subscribe tool."""
        body = await request.json()
        sub_id = _msg_bus.subscribe(channel=body.get("channel"), agent_id=body.get("agent_id"))
        return JSONResponse(content={"status": "subscribed", "subscription_id": sub_id, "channel": body.get("channel"), "agent_id": body.get("agent_id")})

    @app.post("/tools/observability_metrics/execute")
    async def api_observability_metrics():
        """REST endpoint for observability_metrics tool."""
        metrics = {
            "total_executions": _observability.total_executions,
            "success_rate_pct": _observability.success_rate,
            "avg_execution_time_sec": _observability.avg_execution_time,
            "avg_execution_time_success_sec": _observability.avg_execution_time_success,
            "avg_execution_time_failure_sec": _observability.avg_execution_time_failure,
            "error_type_distribution": _observability.error_type_distribution,
            "top_slow_skills": _observability.get_top_slow_skills(5),
            "error_summary": _observability.get_error_summary(),
        }
        return JSONResponse(content=metrics)

    @app.post("/tools/heal_suggestion/execute")
    async def api_heal_suggestion(request: Request):
        """REST endpoint for heal_suggestion tool."""
        body = await request.json()
        suggestion = _heal_cache.find_suggested_fix(
            skill_id=body.get("skill_id"),
            error_type=body.get("error_type"),
            error_msg=body.get("error_msg"),
        )
        if suggestion:
            return JSONResponse(content={
                "status": "suggestion_found",
                "pattern_id": suggestion.pattern_id,
                "fix_description": suggestion.fix_description,
                "fix_code_patch": suggestion.fix_code_patch,
                "success_rate": suggestion.success_count / (suggestion.success_count + suggestion.failure_count) if (suggestion.success_count + suggestion.failure_count) > 0 else 0.0,
            })
        return JSONResponse(content={"status": "no_suggestion", "message": "No learned fix found for this error pattern."})

    return app
