import asyncio
import json
import sqlite3
from typing import Any, Dict, List
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from mcp.server import MCPServer
import mcp.types as types

from autopoiesis.registry.manager import RegistryManager
from autopoiesis.sandbox.executor import SandboxExecutor
from autopoiesis.core.intent import LookAheadParser, ProjectConfig


def create_mcp_server(base_dir: str = ".autopoiesis") -> MCPServer:
    """Creates and configures an MCP Server instance exposing Level 1 & Level 2 active micro-skills."""
    app_server = MCPServer("autopoiesis-mcp-server")

    def get_registry():
        return RegistryManager(base_dir=base_dir)

    # Register primary project orchestrator tool: execute_macro_intent
    async def execute_macro_intent_handler(intent: str, active_namespaces: List[str] = None) -> str:
        reg = get_registry()
        parser = LookAheadParser(reg)
        config = ProjectConfig(
            project_id="mcp_intent_exec",
            active_namespaces=active_namespaces or ["global"],
            required_pipeline_intent=intent,
        )
        results = parser.resolve_pipeline_intent(config)
        output_data = [res.model_dump() for res in results]
        return json.dumps({"intent": intent, "steps": output_data}, indent=2)

    app_server.add_tool(
        fn=execute_macro_intent_handler,
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
                    reg = get_registry()
                    skill = reg.get_skill(s_id)
                    if not skill or not skill.file_path:
                        return json.dumps({"isError": True, "error": f"Skill '{s_id}' not found."})
                    python_code = open(skill.file_path, "r", encoding="utf-8").read()
                    res = SandboxExecutor.execute_skill_code(python_code, kwargs)
                    if not res.success:
                        return json.dumps({"isError": True, "error_type": res.error_type, "stderr": res.stderr})
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
    server = create_mcp_server()
    await server.run_stdio_async()


def create_fastapi_app(base_dir: str = ".autopoiesis") -> FastAPI:
    """Creates FastAPI app for HTTP and SSE transport mode."""
    app = FastAPI(title="Autopoiesis Engine MCP Daemon")

    @app.get("/")
    async def root():
        return {
            "name": "Autopoiesis Engine MCP Daemon",
            "version": "0.1.0",
            "status": "online",
            "endpoints": {
                "list_tools": "/tools",
                "execute_tool": "/tools/{skill_id}/execute",
                "sse": "/sse",
                "messages": "/messages"
            }
        }

    @app.get("/tools")
    async def list_tools():
        registry = RegistryManager(base_dir=base_dir)
        tools = [
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

    @app.post("/tools/{skill_id:path}/execute")
    async def execute_tool(skill_id: str, request: Request):
        registry = RegistryManager(base_dir=base_dir)
        payload = await request.json()

        if skill_id == "execute_macro_intent":
            intent = payload.get("intent", "")
            active_namespaces = payload.get("active_namespaces", ["global"])
            parser = LookAheadParser(registry)
            config = ProjectConfig(
                project_id="http_intent_exec",
                active_namespaces=active_namespaces,
                required_pipeline_intent=intent,
            )
            results = parser.resolve_pipeline_intent(config)
            return {"intent": intent, "steps": [r.model_dump() for r in results]}

        skill = registry.get_skill(skill_id)
        if not skill or not skill.file_path:
            return JSONResponse(
                status_code=404,
                content={"isError": True, "error": f"Skill '{skill_id}' not found."}
            )

        python_code = open(skill.file_path, "r", encoding="utf-8").read()
        res = SandboxExecutor.execute_skill_code(python_code, payload)
        if not res.success:
            return JSONResponse(
                status_code=400,
                content={
                    "isError": True,
                    "error_type": res.error_type,
                    "stderr": res.stderr,
                }
            )
        return res.output_payload

    @app.get("/sse")
    async def handle_sse(request: Request):
        """MCP Server-Sent Events (SSE) connection endpoint."""
        async def event_generator():
            # Initial endpoint event per MCP SSE specification
            yield {
                "event": "endpoint",
                "data": "/messages?session_id=autopoiesis_local"
            }
            while True:
                if await request.is_disconnected():
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
            registry = RegistryManager(base_dir=base_dir)
            tools = [
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

        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    return app
