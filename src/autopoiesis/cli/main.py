import argparse
import sys
import shutil
import json
from pathlib import Path
import uvicorn

from autopoiesis.cli.init import init_workspace, update_mcp_config_file, get_client_config_paths, PlatformAdapter
from autopoiesis.mcp.server import run_mcp_stdio_server, create_fastapi_app


def install_mcp_configs(target_path: str = ".") -> None:
    """Forces generation and overwriting of MCP config files in workspace and client paths."""
    root = PlatformAdapter.sanitize_path(target_path)
    print(f"Installing/Updating MCP configurations for workspace at {root}...")

    local_mcp_path = root / "mcp.json"
    update_mcp_config_file(local_mcp_path)
    print(f"Updated: {local_mcp_path}")

    client_paths = get_client_config_paths()
    for client, path in client_paths.items():
        try:
            update_mcp_config_file(path)
            print(f"Updated {client} config: {path}")
        except Exception as e:
            print(f"Could not update {client} config ({path}): {e}")

    print("MCP configuration update complete.")


def clean_workspace(target_path: str = ".") -> None:
    """Purges runtime state (.autopoiesis), workspace registry files, and mcp configs."""
    root = PlatformAdapter.sanitize_path(target_path)
    print(f"Cleaning workspace at {root}...")

    base_dir = root / ".autopoiesis"
    registry_dir = root / "registry"
    mcp_file = root / "mcp.json"
    rules_file = root / ".cursorrules"

    if base_dir.exists():
        shutil.rmtree(base_dir, ignore_errors=True)
        print("Purged .autopoiesis/ runtime directory.")

    if registry_dir.exists():
        shutil.rmtree(registry_dir, ignore_errors=True)
        print("Purged registry/ workspace directory.")

    if mcp_file.exists():
        mcp_file.unlink(missing_ok=True)
        print("Removed mcp.json file.")

    if rules_file.exists():
        rules_file.unlink(missing_ok=True)
        print("Removed .cursorrules file.")

    print("Workspace clean completed.")


def main():
    parser = argparse.ArgumentParser(description="Autopoiesis Engine CLI Tool")
    subparsers = parser.add_subparsers(dest="command")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize workspace and IDE MCP configurations.")
    init_parser.add_argument("--path", default=".", help="Project path to initialize.")

    # mcp-install command
    mcp_parser = subparsers.add_parser("mcp-install", help="Force overwrite MCP configuration files for IDEs.")
    mcp_parser.add_argument("--path", default=".", help="Project path to update.")

    # clean command
    clean_parser = subparsers.add_parser("clean", help="Purge runtime state (.autopoiesis) and legacy workspace files.")
    clean_parser.add_argument("--path", default=".", help="Project path to clean.")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Run the MCP server daemon.")
    serve_parser.add_argument("--mode", choices=["stdio", "http"], default="stdio", help="Transport mode.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP mode.")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port for HTTP mode.")

    # synthesize command
    synth_parser = subparsers.add_parser("synthesize", help="Synthesize and register a new micro-skill from a description.")
    synth_parser.add_argument("description", help="Natural language description of the skill to create.")
    synth_parser.add_argument("--namespace", default="global", help="Namespace for the skill (default: global).")
    synth_parser.add_argument("--test", action="store_true", help="Test the synthesized skill with a default payload.")
    synth_parser.add_argument("--json", action="store_true", help="Output result as JSON.")

    # amf command group
    amf_parser = subparsers.add_parser("amf", help="AMF agent lifecycle and workflow management.")
    amf_sub = amf_parser.add_subparsers(dest="amf_command")

    # amf init
    amf_init = amf_sub.add_parser("init", help="Initialize AMF workspace structure and create template manifest.")
    amf_init.add_argument("--path", default=".", help="Project path to initialize.")

    # amf register
    amf_reg = amf_sub.add_parser("register", help="Register an AMF agent from a manifest file.")
    amf_reg.add_argument("manifest", help="Path to AMF manifest JSON/YAML file.")

    # amf start
    amf_start = amf_sub.add_parser("start", help="Start a registered AMF agent.")
    amf_start.add_argument("agent_id", help="Agent ID to start.")

    # amf stop
    amf_stop = amf_sub.add_parser("stop", help="Stop a running AMF agent.")
    amf_stop.add_argument("agent_id", help="Agent ID to stop.")

    # amf invoke
    amf_invoke = amf_sub.add_parser("invoke", help="Invoke a capability on an AMF agent.")
    amf_invoke.add_argument("agent_id", help="Agent ID.")
    amf_invoke.add_argument("capability", help="Capability name to invoke.")
    amf_invoke.add_argument("--inputs", default="{}", help="JSON string of inputs.")

    # amf status
    amf_status = amf_sub.add_parser("status", help="Get status of an AMF agent.")
    amf_status.add_argument("agent_id", help="Agent ID.")

    # amf list
    amf_list = amf_sub.add_parser("list", help="List all registered AMF agents.")

    # amf destroy
    amf_destroy = amf_sub.add_parser("destroy", help="Destroy an AMF agent.")
    amf_destroy.add_argument("agent_id", help="Agent ID to destroy.")

    # amf pause
    amf_pause = amf_sub.add_parser("pause", help="Pause a running AMF agent.")
    amf_pause.add_argument("agent_id", help="Agent ID to pause.")

    # amf resume
    amf_resume = amf_sub.add_parser("resume", help="Resume a paused AMF agent.")
    amf_resume.add_argument("agent_id", help="Agent ID to resume.")

    # amf inspect
    amf_inspect = amf_sub.add_parser("inspect", help="Show detailed agent definition and status.")
    amf_inspect.add_argument("agent_id", help="Agent ID to inspect.")

    # amf logs
    amf_logs = amf_sub.add_parser("logs", help="Show recent execution logs for an agent.")
    amf_logs.add_argument("agent_id", help="Agent ID.")
    amf_logs.add_argument("--limit", type=int, default=20, help="Number of log entries to show.")

    # amf health
    amf_health = amf_sub.add_parser("health", help="Run health check on an AMF agent.")
    amf_health.add_argument("agent_id", help="Agent ID to check.")

    # amf heal
    amf_heal = amf_sub.add_parser("heal", help="Get healing suggestion for a failed capability.")
    amf_heal.add_argument("agent_id", help="Agent ID.")
    amf_heal.add_argument("capability", help="Capability name that failed.")
    amf_heal.add_argument("error_type", help="Error type (schema, resource, network, logic).")
    amf_heal.add_argument("error_msg", help="Error message text.")

    # amf workflow register
    amf_wf_reg = amf_sub.add_parser("workflow-register", help="Register a workflow definition from JSON.")
    amf_wf_reg.add_argument("workflow_json", help="Path to workflow definition JSON file.")

    # amf workflow run
    amf_wf_run2 = amf_sub.add_parser("workflow-run", help="Run a registered AMF workflow by ID.")
    amf_wf_run2.add_argument("workflow_id", help="Workflow ID to run.")
    amf_wf_run2.add_argument("--params", default="{}", help="JSON string of parameters.")

    args = parser.parse_args()

    if args.command == "init":
        res = init_workspace(args.path)
        print(f"Workspace initialized successfully at {res['workspace_root']}")
        print(f"Configured MCP clients: {', '.join(res['configured_clients'])}")
        print(f"Generated MCP config: {res['mcp_config_path']}")
    elif args.command == "mcp-install":
        install_mcp_configs(args.path)
    elif args.command == "clean":
        clean_workspace(args.path)
    elif args.command == "serve":
        if args.mode == "stdio":
            import asyncio
            asyncio.run(run_mcp_stdio_server())
        else:
            app = create_fastapi_app()
            uvicorn.run(app, host=args.host, port=args.port)
    elif args.command == "synthesize":
        from autopoiesis.registry.manager import RegistryManager
        from autopoiesis.core.intent import LookAheadParser
        from autopoiesis.sandbox.executor import SandboxExecutor
        
        base_dir = Path(".autopoiesis")
        if not base_dir.exists():
            print("Error: .autopoiesis directory not found. Run 'autopoiesis init' first.")
            sys.exit(1)
        
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        
        print(f"Synthesizing skill from description: '{args.description}'")
        skill_meta = parser.synthesize_and_register_skill(
            step_description=args.description,
            namespace=args.namespace,
            root_registry_dir=Path("registry"),
        )
        
        result = {
            "skill_id": skill_meta.id,
            "namespace": skill_meta.namespace,
            "scope_level": skill_meta.scope_level,
            "description": skill_meta.description,
            "file_path": str(skill_meta.file_path),
        }
        
        if args.test:
            print("Testing synthesized skill...")
            skill = registry.get_skill(skill_meta.id)
            if skill and skill.file_path:
                python_code = open(skill.file_path, "r", encoding="utf-8").read()
                exec_res = SandboxExecutor.execute_skill_code(python_code, {"payload": "test_input"})
                result["test_result"] = {
                    "success": exec_res.success,
                    "output": exec_res.output_payload,
                    "stdout": exec_res.stdout,
                    "stderr": exec_res.stderr,
                    "execution_time_sec": exec_res.execution_time_sec,
                }
                if exec_res.success:
                    print(f"Test PASSED in {exec_res.execution_time_sec:.3f}s")
                else:
                    print(f"Test FAILED: {exec_res.stderr}")
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\nSkill synthesized successfully!")
            print(f"  ID: {result['skill_id']}")
            print(f"  Namespace: {result['namespace']}")
            print(f"  Scope: {result['scope_level']}")
            print(f"  File: {result['file_path']}")
            if args.test and "test_result" in result:
                print(f"  Test: {'PASSED' if result['test_result']['success'] else 'FAILED'}")
    elif args.command == "amf":
        from autopoiesis.amf.lifecycle import AgentLifecycle
        from autopoiesis.amf.orchestrator import AMFOrchestrator
        from autopoiesis.amf.registry import AMFRegistry
        from autopoiesis.amf.schema import WorkflowDef, WorkflowNode, WorkflowEdge
        from autopoiesis.registry.manager import RegistryManager

        base_dir = Path(".autopoiesis")
        if not base_dir.exists():
            print("Error: .autopoiesis directory not found. Run 'autopoiesis init' first.")
            sys.exit(1)

        lifecycle = AgentLifecycle(base_dir=base_dir)
        orchestrator = AMFOrchestrator(base_dir=base_dir)

        if args.amf_command == "init":
            from autopoiesis.amf.cli import cmd_init
            cmd_init(path=args.path)
        elif args.amf_command == "register":
            manifest_path = Path(args.manifest)
            if not manifest_path.exists():
                print(f"Error: Manifest file not found: {manifest_path}")
                sys.exit(1)
            amf_reg = AMFRegistry(base_dir=base_dir)
            try:
                records = amf_reg.register_manifest(manifest_path)
                print(f"Registered {len(records)} agents from manifest.")
                for r in records:
                    print(f"  - {r.agent_id} ({r.namespace}) state={r.state}")
            except Exception as e:
                print(f"Error registering manifest: {e}")
                sys.exit(1)

        elif args.amf_command == "start":
            try:
                state = lifecycle.start_agent(args.agent_id)
                print(f"Agent '{args.agent_id}' started. state={state.state}")
            except Exception as e:
                print(f"Error starting agent: {e}")
                sys.exit(1)

        elif args.amf_command == "stop":
            try:
                state = lifecycle.stop_agent(args.agent_id)
                print(f"Agent '{args.agent_id}' stopped. state={state.state}")
            except Exception as e:
                print(f"Error stopping agent: {e}")
                sys.exit(1)

        elif args.amf_command == "invoke":
            try:
                inputs = json.loads(args.inputs)
            except json.JSONDecodeError as e:
                print(f"Error parsing inputs JSON: {e}")
                sys.exit(1)
            from autopoiesis.amf.runtime import AMFRuntime
            runtime = AMFRuntime(base_dir=base_dir)
            result = runtime.invoke_capability(args.agent_id, args.capability, inputs)
            if result.success:
                print(json.dumps(result.output, indent=2))
            else:
                print(f"Error: {result.stderr}")
                sys.exit(1)

        elif args.amf_command == "status":
            status = lifecycle.get_agent_status(args.agent_id)
            if status:
                print(json.dumps(status, indent=2))
            else:
                print(f"Agent '{args.agent_id}' not found.")
                sys.exit(1)

        elif args.amf_command == "list":
            agents = lifecycle.list_agents()
            print(json.dumps(agents, indent=2))

        elif args.amf_command == "destroy":
            ok = lifecycle.destroy_agent(args.agent_id)
            if ok:
                print(f"Agent '{args.agent_id}' destroyed.")
            else:
                print(f"Agent '{args.agent_id}' not found.")
                sys.exit(1)

        elif args.amf_command == "pause":
            try:
                state = lifecycle.pause_agent(args.agent_id)
                print(f"Agent '{args.agent_id}' paused. state={state.state}")
            except Exception as e:
                print(f"Error pausing agent: {e}")
                sys.exit(1)

        elif args.amf_command == "resume":
            try:
                state = lifecycle.resume_agent(args.agent_id)
                print(f"Agent '{args.agent_id}' resumed. state={state.state}")
            except Exception as e:
                print(f"Error resuming agent: {e}")
                sys.exit(1)

        elif args.amf_command == "inspect":
            from autopoiesis.amf.metrics import AMFMetricsAdapter
            from autopoiesis.amf.healing import AMFHealingAdapter
            status = lifecycle.get_agent_status(args.agent_id)
            if not status:
                print(f"Agent '{args.agent_id}' not found.", file=sys.stderr)
                sys.exit(1)
            print(f"Agent: {args.agent_id}")
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
            metrics = AMFMetricsAdapter(base_dir=base_dir)
            health = metrics.get_agent_health(args.agent_id)
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
            healing = AMFHealingAdapter(base_dir=base_dir)
            patterns = healing.get_patterns_for_agent(args.agent_id)
            if patterns:
                print(f"\n--- Learned Healing Patterns ({len(patterns)}) ---")
                for p in patterns[:5]:
                    print(f"  [{p['error_type']}] {p['fix_description']} (success_rate={p['success_rate']:.2f})")

        elif args.amf_command == "logs":
            from autopoiesis.core.session import AgentSessionManager
            status = lifecycle.get_agent_status(args.agent_id)
            if not status or not status.get("session_id"):
                print(f"Agent '{args.agent_id}' not found or has no session.", file=sys.stderr)
                sys.exit(1)
            session_mgr = AgentSessionManager(base_dir=base_dir)
            history = session_mgr.get_recent_history(status["session_id"], limit=getattr(args, 'limit', 20))
            if not history:
                print(f"No execution history for agent '{args.agent_id}'.")
                return
            print(f"Recent {len(history)} executions for '{args.agent_id}':")
            print("-" * 60)
            for entry in history:
                status_str = "SUCCESS" if entry["success"] else f"FAIL [{entry.get('error', '')[:50]}]"
                print(f"[{entry['timestamp']}] {entry['tool']}: {status_str}")

        elif args.amf_command == "health":
            from autopoiesis.amf.runtime import AMFRuntime
            runtime = AMFRuntime(base_dir=base_dir)
            health = runtime.health_check(args.agent_id)
            print(json.dumps(health, indent=2))

        elif args.amf_command == "heal":
            from autopoiesis.amf.healing import AMFHealingAdapter
            healing = AMFHealingAdapter(base_dir=base_dir)
            suggestion = healing.heal_capability_failure(
                agent_id=args.agent_id,
                capability=args.capability,
                error_type=args.error_type,
                error_msg=args.error_msg,
            )
            print(json.dumps(suggestion.model_dump(), indent=2))

        elif args.amf_command == "workflow-run":
            try:
                params = json.loads(args.params)
            except json.JSONDecodeError as e:
                print(f"Error parsing params JSON: {e}")
                sys.exit(1)
            try:
                result = orchestrator.run_workflow_by_id(args.workflow_id, parameters=params)
                print(json.dumps(result.model_dump(), indent=2))
            except Exception as e:
                print(f"Error running workflow: {e}")
                sys.exit(1)

        elif args.amf_command == "workflow-register":
            wf_path = Path(args.workflow_json)
            if not wf_path.exists():
                print(f"Error: Workflow JSON file not found: {wf_path}")
                sys.exit(1)
            try:
                wf_data = json.loads(wf_path.read_text(encoding="utf-8"))
                wf_def = WorkflowDef(**wf_data)
                ok = orchestrator.register_workflow(wf_def)
                if ok:
                    print(f"Workflow '{wf_def.workflow_id}' registered successfully.")
                else:
                    print("Failed to register workflow.")
                    sys.exit(1)
            except Exception as e:
                print(f"Error registering workflow: {e}")
                sys.exit(1)
        else:
            amf_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
