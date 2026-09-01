"""AMF CLI — command-line interface for AMF agent management."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.amf.registry import AMFRegistry
from autopoiesis.amf.lifecycle import AgentLifecycle
from autopoiesis.amf.runtime import AMFRuntime
from autopoiesis.amf.bus import AMFBusAdapter
from autopoiesis.amf.metrics import AMFMetricsAdapter
from autopoiesis.amf.healing import AMFHealingAdapter
from autopoiesis.amf.orchestrator import AMFOrchestrator
from autopoiesis.amf.schema import AMFManifest, AgentDef, WorkflowDef


def _get_base_dir(path: str = ".") -> Path:
    return PlatformAdapter.sanitize_path(path)


def _get_components(base_dir: Path):
    """Returns initialized AMF components."""
    registry = AMFRegistry(base_dir=base_dir)
    lifecycle = AgentLifecycle(base_dir=base_dir)
    runtime = AMFRuntime(base_dir=base_dir)
    bus = AMFBusAdapter(base_dir=base_dir)
    metrics = AMFMetricsAdapter(base_dir=base_dir)
    healing = AMFHealingAdapter(base_dir=base_dir)
    orchestrator = AMFOrchestrator(base_dir=base_dir)
    return registry, lifecycle, runtime, bus, metrics, healing, orchestrator


def cmd_init(path: str = ".") -> None:
    """Initializes AMF workspace structure and creates template manifest."""
    base_dir = _get_base_dir(path)
    base_dir.mkdir(parents=True, exist_ok=True)

    amf_dir = base_dir / "amf"
    amf_dir.mkdir(parents=True, exist_ok=True)
    (amf_dir / "manifests").mkdir(parents=True, exist_ok=True)
    (amf_dir / "workflows").mkdir(parents=True, exist_ok=True)

    # Create template manifest
    template_manifest = AMFManifest(
        project="my-amf-project",
        agents=[
            AgentDef(
                agent_id="example_agent",
                namespace="global",
                version="1.0.0",
                description="Example AMF agent template",
                capabilities=[
                    Capability(
                        name="example_capability",
                        skill_id="core_data_utilities",
                        inputs={"type": "object", "properties": {"data": {}}},
                        outputs={"type": "object", "properties": {"status": {"type": "string"}}},
                    )
                ],
                dependencies=[],
                metadata={"owner": "amf_user"},
                lifecycle_hooks=LifecycleHooks(on_start=[], on_stop=[]),
            )
        ],
    )

    manifest_path = amf_dir / "manifests" / "example_manifest.yaml"
    try:
        import yaml
        manifest_path.write_text(
            yaml.dump(template_manifest.model_dump(), default_flow_style=False),
            encoding="utf-8",
        )
    except ImportError:
        manifest_path.write_text(
            json.dumps(template_manifest.model_dump(), indent=2),
            encoding="utf-8",
        )

    print(f"AMF workspace initialized at {base_dir}")
    print(f"Template manifest: {manifest_path}")


def cmd_register(manifest_path: str, base_dir: str = ".") -> None:
    """Registers agents from an AMF manifest file."""
    base = _get_base_dir(base_dir)
    registry, _, _, _, _, _, _ = _get_components(base)

    try:
        records = registry.register_manifest(manifest_path)
        for record in records:
            print(f"Registered agent: {record.agent_id} (namespace={record.namespace}, state={record.state})")
    except Exception as e:
        print(f"Failed to register manifest: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(base_dir: str = ".", namespace: Optional[str] = None, state: Optional[str] = None) -> None:
    """Lists all registered AMF agents."""
    base = _get_base_dir(base_dir)
    _, lifecycle, _, _, _, _, _ = _get_components(base)

    agents = lifecycle.list_agents(namespace=namespace, state=state)
    if not agents:
        print("No agents found.")
        return

    print(f"{'AGENT_ID':<30} {'STATE':<12} {'NAMESPACE':<15} {'CAPABILITIES'}")
    print("-" * 80)
    for agent in agents:
        caps = ", ".join(agent.get("capabilities", []))
        print(f"{agent['agent_id']:<30} {agent['state']:<12} {agent['namespace']:<15} {caps}")


def cmd_start(agent_id: str, base_dir: str = ".") -> None:
    """Starts an AMF agent."""
    base = _get_base_dir(base_dir)
    _, lifecycle, _, _, _, _, _ = _get_components(base)

    try:
        state = lifecycle.start_agent(agent_id)
        print(f"Agent '{agent_id}' started. State: {state.state}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_stop(agent_id: str, base_dir: str = ".") -> None:
    """Stops an AMF agent."""
    base = _get_base_dir(base_dir)
    _, lifecycle, _, _, _, _, _ = _get_components(base)

    try:
        state = lifecycle.stop_agent(agent_id)
        print(f"Agent '{agent_id}' stopped. State: {state.state}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_pause(agent_id: str, base_dir: str = ".") -> None:
    """Pauses an AMF agent."""
    base = _get_base_dir(base_dir)
    _, lifecycle, _, _, _, _, _ = _get_components(base)

    try:
        state = lifecycle.pause_agent(agent_id)
        print(f"Agent '{agent_id}' paused. State: {state.state}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_resume(agent_id: str, base_dir: str = ".") -> None:
    """Resumes a paused AMF agent."""
    base = _get_base_dir(base_dir)
    _, lifecycle, _, _, _, _, _ = _get_components(base)

    try:
        state = lifecycle.resume_agent(agent_id)
        print(f"Agent '{agent_id}' resumed. State: {state.state}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_inspect(agent_id: str, base_dir: str = ".") -> None:
    """Shows detailed agent definition and status."""
    base = _get_base_dir(base_dir)
    _, lifecycle, _, _, metrics, healing, _ = _get_components(base)

    status = lifecycle.get_agent_status(agent_id)
    if not status:
        print(f"Agent '{agent_id}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Agent: {agent_id}")
    print(f"State: {status['state']}")
    print(f"Namespace: {status['namespace']}")
    print(f"Version: {status['version']}")
    print(f"Description: {status['description']}")
    print(f"Session ID: {status['session_id']}")
    print(f"Capabilities: {', '.join(status['capabilities'])}")
    print(f"Dependencies: {', '.join(status['dependencies'])}")
    print(f"Created: {status['created_at']}")
    print(f"Updated: {status['updated_at']}")
    print(f"Dependencies Satisfied: {status.get('dependencies_satisfied', 'N/A')}")
    if status.get('missing_dependencies'):
        print(f"Missing Dependencies: {', '.join(status['missing_dependencies'])}")
    if status.get('memory_keys'):
        print(f"Memory Keys: {', '.join(status['memory_keys'])}")

    # Health metrics
    health = metrics.get_agent_health(agent_id)
    print(f"\n--- Health Metrics ---")
    print(f"Total Executions: {health.total_executions}")
    print(f"Success Rate: {health.success_rate}%")
    print(f"Avg Execution Time: {health.avg_execution_time}s")
    if health.error_distribution:
        print(f"Error Distribution: {json.dumps(health.error_distribution)}")
    if health.top_slow_capabilities:
        print("Top Slow Capabilities:")
        for cap in health.top_slow_capabilities:
            print(f"  - {cap['capability']}: {cap['avg_time']}s ({cap['executions']} executions)")

    # Learned healing patterns
    patterns = healing.get_patterns_for_agent(agent_id)
    if patterns:
        print(f"\n--- Learned Healing Patterns ({len(patterns)}) ---")
        for p in patterns[:5]:
            print(f"  [{p['error_type']}] {p['fix_description']} (success_rate={p['success_rate']:.2f})")


def cmd_logs(agent_id: str, base_dir: str = ".", limit: int = 20) -> None:
    """Shows recent execution logs for an agent."""
    base = _get_base_dir(base_dir)
    _, lifecycle, _, _, _, _, _ = _get_components(base)

    status = lifecycle.get_agent_status(agent_id)
    if not status or not status.get("session_id"):
        print(f"Agent '{agent_id}' not found or has no session.", file=sys.stderr)
        sys.exit(1)

    from autopoiesis.core.session import AgentSessionManager
    session_mgr = AgentSessionManager(base_dir=base)
    history = session_mgr.get_recent_history(status["session_id"], limit=limit)

    if not history:
        print(f"No execution history for agent '{agent_id}'.")
        return

    print(f"Recent {len(history)} executions for '{agent_id}':")
    print("-" * 60)
    for entry in history:
        status_str = "SUCCESS" if entry["success"] else f"FAIL [{entry.get('error', '')[:50]}]"
        print(f"[{entry['timestamp']}] {entry['tool']}: {status_str}")


def cmd_run(
    agent_id: str,
    capability: str,
    input_json: str,
    base_dir: str = ".",
) -> None:
    """Invokes a capability on an agent."""
    base = _get_base_dir(base_dir)
    _, _, runtime, _, metrics, _, _ = _get_components(base)

    try:
        inputs = json.loads(input_json)
    except json.JSONDecodeError:
        print(f"Invalid JSON input: {input_json}", file=sys.stderr)
        sys.exit(1)

    result = runtime.invoke_capability(agent_id=agent_id, capability_name=capability, inputs=inputs)

    # Record metrics
    skill_id = f"direct.{capability}"
    metrics.record_capability_invocation(
        agent_id=agent_id,
        capability=capability,
        skill_id=skill_id,
        success=result.success,
        execution_time_sec=result.execution_time_sec,
        error_type=result.error_type,
    )

    if result.success:
        print(json.dumps({"status": "success", "output": result.output}, indent=2))
    else:
        print(json.dumps({
            "status": "error",
            "error": result.stderr,
            "error_type": result.error_type,
            "execution_time_sec": result.execution_time_sec,
        }, indent=2), file=sys.stderr)
        sys.exit(1)


def cmd_health(agent_id: str, base_dir: str = ".") -> None:
    """Runs health check on an agent."""
    base = _get_base_dir(base_dir)
    _, _, runtime, _, _, _, _ = _get_components(base)

    health = runtime.health_check(agent_id)
    print(json.dumps(health, indent=2))


def cmd_heal(
    agent_id: str,
    capability: str,
    error_type: str,
    error_msg: str,
    base_dir: str = ".",
) -> None:
    """Gets healing suggestion for a failed capability."""
    base = _get_base_dir(base_dir)
    _, _, _, _, _, healing, _ = _get_components(base)

    suggestion = healing.heal_capability_failure(
        agent_id=agent_id,
        capability=capability,
        error_type=error_type,
        error_msg=error_msg,
    )

    print(json.dumps(suggestion.model_dump(), indent=2))


def cmd_workflow_run(
    workflow_file: str,
    base_dir: str = ".",
    parameters_json: str = "{}",
) -> None:
    """Runs a workflow from a JSON file."""
    base = _get_base_dir(base_dir)
    _, _, _, _, _, _, orchestrator = _get_components(base)

    try:
        workflow_data = json.loads(Path(workflow_file).read_text(encoding="utf-8"))
        workflow_def = WorkflowDef(**workflow_data)
        parameters = json.loads(parameters_json)
    except Exception as e:
        print(f"Failed to load workflow: {e}", file=sys.stderr)
        sys.exit(1)

    result = orchestrator.run_workflow(workflow_def=workflow_def, parameters=parameters)
    print(json.dumps(result.model_dump(), indent=2))


# Import Capability and LifecycleHooks for cmd_init
from autopoiesis.amf.schema import Capability, LifecycleHooks
