import asyncio
import json
import sqlite3
from typing import Any, Dict, List
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from autopoiesis.registry.manager import RegistryManager
from autopoiesis.sandbox.executor import SandboxExecutor


def create_mcp_server(base_dir: str = ".autopoiesis") -> Server:
    """Creates and configures an MCP Server instance exposing Level 1 & Level 2 active micro-skills."""
    app_server = Server("autopoiesis-mcp-server")
    registry = RegistryManager(base_dir=base_dir)

    @app_server.list_tools()
    async def handle_list_tools() -> List[types.Tool]:
        tools: List[types.Tool] = []
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, description, inputs_json FROM skills")
            rows = cursor.fetchall()
            for row in rows:
                skill_id, desc, inputs_json = row[0], row[1], row[2]
                input_schema = json.loads(inputs_json)
                tools.append(
                    types.Tool(
                        name=skill_id,
                        description=desc or f"Skill {skill_id}",
                        inputSchema=input_schema if isinstance(input_schema, dict) else {"type": "object", "properties": {}},
                    )
                )
        return tools

    @app_server.call_tool()
    async def handle_call_tool(name: str, arguments: Dict[str, Any] | None) -> List[types.TextContent]:
        skill = registry.get_skill(name)
        if not skill:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"isError": True, "error": f"Skill '{name}' not found in registry."})
                )
            ]

        if not skill.file_path:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"isError": True, "error": f"Skill path missing for '{name}'."})
                )
            ]

        python_code = open(skill.file_path, "r", encoding="utf-8").read()
        res = SandboxExecutor.execute_skill_code(python_code, arguments or {})

        if not res.success:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "isError": True,
                        "error_type": res.error_type,
                        "stderr": res.stderr,
                        "stdout": res.stdout,
                    })
                )
            ]

        return [
            types.TextContent(
                type="text",
                text=json.dumps(res.output_payload, indent=2)
            )
        ]

    return app_server


async def run_mcp_stdio_server():
    """Runs the MCP server over stdio transport."""
    server = create_mcp_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="autopoiesis-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


def create_fastapi_app() -> FastAPI:
    """Creates FastAPI app for HTTP/SSE transport mode."""
    app = FastAPI(title="Autopoiesis Engine MCP Daemon")
    registry = RegistryManager()

    @app.get("/tools")
    async def list_tools():
        server = create_mcp_server()
        # Direct json output of available tools
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, namespace, scope_level, description, inputs_json FROM skills")
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "namespace": r[1],
                    "scope_level": r[2],
                    "description": r[3],
                    "inputs": json.loads(r[4])
                }
                for r in rows
            ]

    @app.post("/tools/{skill_id:path}/execute")
    async def execute_tool(skill_id: str, request: Request):
        payload = await request.json()
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

    return app
