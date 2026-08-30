import asyncio
import json
import sqlite3
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
from autopoiesis.cli.init import init_workspace, PlatformAdapter
from autopoiesis.mcp.dashboard import DASHBOARD_HTML

# ANSI Color constants for visual terminal feedback
RESET = "\033[0m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"


def log_visual_activity(tag: str, message: str, color: str = CYAN):
    """Prints a highlighted real-time visual console log entry."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{BOLD}{color}[AUTOPOIESIS | {timestamp}] [{tag}]{RESET} {message}", flush=True)


def ensure_workspace_initialized(base_dir: str = ".autopoiesis"):
    """Automatically self-initializes the workspace if database or registry is missing."""
    import os
    db_file = os.path.join(base_dir, "autopoiesis.db")
    if not os.path.exists(db_file):
        log_visual_activity("AUTO-INIT", "Workspace not initialized. Auto-running self-initialization...", YELLOW)
        init_workspace(".")
        log_visual_activity("AUTO-INIT", "Workspace & seed database initialized successfully!", GREEN)
    else:
        # Run startup delta indexing reconciliation
        reg = RegistryManager(base_dir=base_dir)
        reg.sync_delta_indexing()


def record_mcp_tool_trace(base_dir: str, skill_id: str, success: bool, output: Dict[str, Any], stdout: str = "", stderr: str = "", execution_time_sec: float = 0.012, error_type: str | None = None):
    """Logs an execution trace file in .autopoiesis/traces/ and updates SQLite execution_history table."""
    b_path = PlatformAdapter.sanitize_path(base_dir)
    traces_dir = b_path / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    exec_uuid = f"mcp_{uuid.uuid4().hex[:8]}"
    trace_file = traces_dir / f"{exec_uuid}.json"

    trace_entry = [{
        "node_id": "mcp_call",
        "skill_id": skill_id,
        "success": success,
        "error_type": error_type,
        "execution_time_sec": execution_time_sec,
        "stdout": stdout or f"Executed tool: {skill_id}",
        "stderr": stderr,
        "output": output,
        "timestamp": datetime.datetime.now().isoformat()
    }]
    trace_file.write_text(json.dumps(trace_entry, indent=2), encoding="utf-8")

    db_path = b_path / "autopoiesis.db"
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_history (
                    id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    execution_time_sec REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                INSERT INTO execution_history (id, skill_id, success, execution_time_sec)
                VALUES (?, ?, ?, ?)
            """, (exec_uuid, skill_id, 1 if success else 0, execution_time_sec))
            conn.commit()
    except Exception:
        pass


def create_mcp_server(base_dir: str = ".autopoiesis") -> MCPServer:
    """Creates and configures an MCP Server instance exposing Level 1 & Level 2 active micro-skills."""
    ensure_workspace_initialized(base_dir)

    app_server = MCPServer("autopoiesis-mcp-server")

    def get_registry():
        return RegistryManager(base_dir=base_dir)

    # Register primary project orchestrator tool: run_intent / execute_macro_intent
    async def run_intent_handler(intent: str, active_namespaces: List[str] = None) -> str:
        log_visual_activity("MCP AGENT ENGAGED", f"Executing intent: '{intent}'", MAGENTA)
        reg = get_registry()
        parser = LookAheadParser(reg)
        config = ProjectConfig(
            project_id="mcp_intent_exec",
            active_namespaces=active_namespaces or ["global"],
            required_pipeline_intent=intent,
        )
        results = parser.resolve_pipeline_intent(config, auto_synthesize=True)
        output_data = [res.model_dump() for res in results]

        record_mcp_tool_trace(
            base_dir=base_dir,
            skill_id="run_intent",
            success=True,
            output={"intent": intent, "steps": output_data},
            stdout=f"Orchestrated intent: '{intent}' -> {len(results)} steps resolved.",
            execution_time_sec=0.025
        )

        log_visual_activity("MCP INTENT COMPLETE", f"Resolved & synthesized {len(results)} execution steps.", GREEN)
        return json.dumps({"intent": intent, "steps": output_data}, indent=2)

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
    log_visual_activity("DAEMON ACTIVE", "Autopoiesis Engine Daemon running in STDIO mode.", BOLD + GREEN)
    server = create_mcp_server()
    await server.run_stdio_async()


def create_fastapi_app(base_dir: str = ".autopoiesis") -> FastAPI:
    """Creates FastAPI app for HTTP and SSE transport mode with Global Agent Dashboard UI."""
    ensure_workspace_initialized(base_dir)
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
                else:
                    variant_count += 1

                # Calculate execution count from traces and SQLite execution_history
                exec_count = 0
                if traces_dir.exists():
                    for t_file in traces_dir.glob("*.json"):
                        try:
                            t_data = json.loads(t_file.read_text(encoding="utf-8"))
                            exec_count += sum(1 for entry in t_data if entry.get("skill_id") == r[0])
                        except Exception:
                            pass

                agents.append({
                    "id": r[0],
                    "namespace": r[1],
                    "scope_level": scope,
                    "description": r[3],
                    "file_path": r[4],
                    "ast_hash": r[5],
                    "execution_count": exec_count
                })

            # Include run_intent and execute_macro_intent orchestrators
            run_intent_count = 0
            if traces_dir.exists():
                for t_file in traces_dir.glob("*.json"):
                    try:
                        t_data = json.loads(t_file.read_text(encoding="utf-8"))
                        run_intent_count += sum(1 for entry in t_data if entry.get("skill_id") in ("run_intent", "execute_macro_intent"))
                    except Exception:
                        pass

            agents.insert(0, {
                "id": "run_intent",
                "namespace": "global",
                "scope_level": "core",
                "description": "Catch-all orchestration tool. Direct natural language execution engine.",
                "file_path": "autopoiesis.core.intent",
                "ast_hash": "N/A",
                "execution_count": run_intent_count
            })

            cursor.execute("SELECT template_id, namespace, description FROM templates")
            for r in cursor.fetchall():
                template_count += 1
                agents.append({
                    "id": r[0],
                    "namespace": r[1],
                    "scope_level": "template",
                    "description": r[2] or "Composite DAG Template",
                    "file_path": f"registry/level_3_templates/{r[1]}/{r[0]}.json",
                    "ast_hash": "N/A",
                    "execution_count": 0
                })

        return {
            "stats": {
                "total": len(agents),
                "core": core_count + 1,
                "variant": variant_count,
                "templates": template_count,
                "execution_runs": execution_runs,
            },
            "agents": agents
        }

    @app.get("/api/dashboard/logs/{agent_id:path}")
    async def api_agent_logs(agent_id: str):
        """API endpoint fetching isolated logs and traces for a specific agent/skill."""
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.get_skill(agent_id)

        traces_dir = PlatformAdapter.sanitize_path(base_dir) / "traces"
        logs = []

        if traces_dir.exists():
            for t_file in traces_dir.glob("*.json"):
                try:
                    t_entries = json.loads(t_file.read_text(encoding="utf-8"))
                    for entry in t_entries:
                        target_id = entry.get("skill_id")
                        if target_id == agent_id or (agent_id in ("run_intent", "execute_macro_intent") and target_id in ("run_intent", "execute_macro_intent")):
                            status_str = "SUCCESS" if entry.get("success") else f"FAIL [{entry.get('error_type')}]"
                            log_msg = f"[{entry.get('timestamp', t_file.stem)}] [Node: {entry.get('node_id')}] Status: {status_str} ({entry.get('execution_time_sec', 0):.3f}s)\n"
                            if entry.get("stdout"):
                                log_msg += f"STDOUT:\n{entry.get('stdout')}\n"
                            if entry.get("stderr"):
                                log_msg += f"STDERR:\n{entry.get('stderr')}\n"
                            if entry.get("output"):
                                log_msg += f"OUTPUT PAYLOAD:\n{json.dumps(entry.get('output'), indent=2)}\n"
                            logs.append(log_msg)
                except Exception:
                    pass

        return {
            "agent_id": agent_id,
            "namespace": skill.namespace if skill else "global",
            "ast_hash": skill.ast_hash if skill else "N/A",
            "logs": logs
        }

    @app.get("/tools")
    async def list_tools():
        log_visual_activity("MCP HANDSHAKE", "AI Agent listed available tools.", CYAN)
        registry = RegistryManager(base_dir=base_dir)
        tools = [
            {
                "id": "run_intent",
                "namespace": "global",
                "scope_level": "core",
                "description": "Catch-all orchestration tool. Pass natural language instructions directly.",
                "inputs": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string"},
                        "active_namespaces": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["intent"]
                }
            },
            {
                "id": "execute_macro_intent",
                "namespace": "global",
                "scope_level": "core",
                "description": "Primary project orchestrator tool for end-to-end intent processing and resolution.",
                "inputs": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string"},
                        "active_namespaces": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["intent"]
                }
            }
        ]
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, namespace, scope_level, description, inputs_json FROM skills")
            rows = cursor.fetchall()
            for r in rows:
                tools.append({
                    "id": r[0],
                    "namespace": r[1],
                    "scope_level": r[2],
                    "description": r[3],
                    "inputs": json.loads(r[4])
                })
        return tools

    @app.get("/resources/registry")
    async def resource_registry():
        """MCP Resource Endpoint: Complete JSON tree of registered Level 1, 2, 3 skills and schemas."""
        registry = RegistryManager(base_dir=base_dir)
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, namespace, scope_level, description, inputs_json, outputs_json, ast_hash FROM skills")
            skills = [
                {
                    "id": r[0],
                    "namespace": r[1],
                    "scope_level": r[2],
                    "description": r[3],
                    "inputs": json.loads(r[4]),
                    "outputs": json.loads(r[5]),
                    "ast_hash": r[6]
                }
                for r in cursor.fetchall()
            ]
            cursor.execute("SELECT template_id, namespace, description, parameters_json, dag_json FROM templates")
            templates = [
                {
                    "template_id": r[0],
                    "namespace": r[1],
                    "description": r[2],
                    "parameters": json.loads(r[3]),
                    "dag": json.loads(r[4])
                }
                for r in cursor.fetchall()
            ]
        return {"resource": "resource://autopoiesis/registry", "skills": skills, "templates": templates}

    @app.get("/resources/state/history")
    async def resource_history():
        """MCP Resource Endpoint: Real-time execution history and trace metrics."""
        traces_dir = PlatformAdapter.sanitize_path(base_dir) / "traces"
        traces_data = []
        if traces_dir.exists():
            for trace_file in traces_dir.glob("*.json"):
                try:
                    traces_data.append({
                        "execution_id": trace_file.stem,
                        "trace": json.loads(trace_file.read_text(encoding="utf-8"))
                    })
                except Exception:
                    pass
        return {"resource": "resource://autopoiesis/state/history", "executions": traces_data}

    @app.get("/resources/config")
    async def resource_config():
        """MCP Resource Endpoint: Active project config and storage paths."""
        return {
            "resource": "resource://autopoiesis/config",
            "base_dir": str(PlatformAdapter.sanitize_path(base_dir)),
            "db_path": str(PlatformAdapter.sanitize_path(base_dir) / "autopoiesis.db"),
            "qdrant_dir": str(PlatformAdapter.sanitize_path(base_dir) / "qdrant"),
            "staging_dir": str(PlatformAdapter.sanitize_path(base_dir) / "staging"),
        }

    @app.post("/tools/{skill_id:path}/execute")
    async def execute_tool(skill_id: str, request: Request):
        registry = RegistryManager(base_dir=base_dir)
        payload = await request.json()

        log_visual_activity("HTTP TOOL CALL", f"AI Agent requested execution of '{skill_id}'", MAGENTA)

        if skill_id in ("run_intent", "execute_macro_intent"):
            intent = payload.get("intent", "")
            active_namespaces = payload.get("active_namespaces", ["global"])
            parser = LookAheadParser(registry)
            config = ProjectConfig(
                project_id="http_intent_exec",
                active_namespaces=active_namespaces,
                required_pipeline_intent=intent,
            )
            results = parser.resolve_pipeline_intent(config, auto_synthesize=True)
            res_dict = {"intent": intent, "steps": [r.model_dump() for r in results]}

            record_mcp_tool_trace(
                base_dir=base_dir,
                skill_id=skill_id,
                success=True,
                output=res_dict,
                stdout=f"Executed intent via HTTP API: '{intent}'",
                execution_time_sec=0.025
            )

            log_visual_activity("HTTP INTENT SUCCESS", f"Intent executed: {len(results)} steps resolved.", GREEN)
            return res_dict

        skill = registry.get_skill(skill_id)
        if not skill or not skill.file_path:
            log_visual_activity("HTTP TOOL ERROR", f"Skill '{skill_id}' not found.", YELLOW)
            err_out = {"isError": True, "error": f"Skill '{skill_id}' not found."}
            record_mcp_tool_trace(base_dir, skill_id, False, err_out, stderr="Skill not found")
            return JSONResponse(status_code=404, content=err_out)

        python_code = open(skill.file_path, "r", encoding="utf-8").read()
        res = SandboxExecutor.execute_skill_code(python_code, payload)

        record_mcp_tool_trace(
            base_dir=base_dir,
            skill_id=skill_id,
            success=res.success,
            output=res.output_payload,
            stdout=res.stdout,
            stderr=res.stderr,
            execution_time_sec=res.execution_time_sec,
            error_type=res.error_type
        )

        if not res.success:
            log_visual_activity("SANDBOX FAIL", f"Skill '{skill_id}' execution failed.", YELLOW)
            return JSONResponse(
                status_code=400,
                content={
                    "isError": True,
                    "error_type": res.error_type,
                    "stderr": res.stderr,
                }
            )
        log_visual_activity("HTTP TOOL SUCCESS", f"Skill '{skill_id}' executed in {res.execution_time_sec:.3f}s", GREEN)
        return res.output_payload

    @app.get("/sse")
    async def handle_sse(request: Request):
        """MCP Server-Sent Events (SSE) connection endpoint."""
        log_visual_activity("MCP SSE CONNECT", "Client connected via Server-Sent Events (/sse).", GREEN)
        async def event_generator():
            yield {
                "event": "endpoint",
                "data": "/messages?session_id=autopoiesis_local"
            }
            while True:
                if await request.is_disconnected():
                    log_visual_activity("MCP SSE DISCONNECT", "Client disconnected from SSE.", YELLOW)
                    break
                await asyncio.sleep(15)
                yield {"event": "ping", "data": "keep-alive"}

        return EventSourceResponse(event_generator())

    @app.post("/messages")
    async def handle_messages(request: Request):
        """MCP SSE messages handler."""
        body = await request.json()
        method = body.get("method")
        msg_id = body.get("id")

        if method == "tools/list":
            log_visual_activity("MCP SSE HANDSHAKE", "Received tools/list request via SSE messages.", CYAN)
            registry = RegistryManager(base_dir=base_dir)
            tools = [
                {
                    "name": "run_intent",
                    "description": "Catch-all orchestration tool. Pass natural language instructions directly.",
                    "inputSchema": {"type": "object", "properties": {"intent": {"type": "string"}}, "required": ["intent"]}
                },
                {
                    "name": "execute_macro_intent",
                    "description": "Primary project orchestrator tool for end-to-end intent processing.",
                    "inputSchema": {"type": "object", "properties": {"intent": {"type": "string"}}, "required": ["intent"]}
                }
            ]
            with sqlite3.connect(registry.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, description, inputs_json FROM skills")
                rows = cursor.fetchall()
                for r in rows:
                    tools.append({
                        "name": r[0],
                        "description": r[1],
                        "inputSchema": json.loads(r[2])
                    })
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}}

        if method == "resources/read":
            uri = body.get("params", {}).get("uri", "")
            registry = RegistryManager(base_dir=base_dir)
            if "registry" in uri:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "contents": [
                            {"uri": uri, "mimeType": "application/json", "text": json.dumps({"status": "active"})}
                        ]
                    }
                }

        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    return app
