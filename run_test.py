import asyncio
import json
import tempfile
from pathlib import Path

from autopoiesis.registry.manager import RegistryManager
from autopoiesis.amf.registry import AMFRegistry
from autopoiesis.amf.schema import AgentDef, Capability
from autopoiesis.amf.lifecycle import AgentLifecycle
from autopoiesis.mcp.server import create_mcp_server

with tempfile.TemporaryDirectory() as tmp_path:
    tmp_path = Path(tmp_path)
    base_dir = tmp_path / ".autopoiesis"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "registry").mkdir(parents=True, exist_ok=True)

    reg = RegistryManager(base_dir=base_dir)
    reg.register_skill(
        skill_id="test.echo",
        namespace="global",
        scope_level="core",
        description="Echo skill",
        inputs={"type": "object", "properties": {"message": {"type": "string"}}},
        outputs={"type": "object", "properties": {"echo": {"type": "string"}}},
        python_code='def main(inputs: dict) -> dict:\n    msg = inputs.get("message", "")\n    return {"status": "success", "echo": msg}\n',
        root_registry_dir=tmp_path / "registry",
    )

    amf_reg = AMFRegistry(base_dir=base_dir)
    amf_reg.register_agent(AgentDef(
        agent_id="mcp_test_agent",
        capabilities=[Capability(name="echo", skill_id="test.echo")],
    ))

    lifecycle = AgentLifecycle(base_dir=base_dir)
    lifecycle.create_agent("mcp_test_agent", metadata={"purpose": "testing"})

    server = create_mcp_server(base_dir=str(base_dir))

    # Monkey-patch amf_list_agents to print what base_dir it receives
    import autopoiesis.mcp.server as mcp_server_module
    original_list_agents = None
    for tool in getattr(server, '_tools', []):
        if hasattr(tool, 'name') and tool.name == 'amf_list_agents':
            original_list_agents = tool.fn
            async def patched_list_agents(base_dir=".autopoiesis"):
                print(f"[PATCHED] amf_list_agents called with base_dir={base_dir!r}")
                result = await original_list_agents(base_dir=base_dir)
                print(f"[PATCHED] amf_list_agents returned: {result}")
                return result
            tool.fn = patched_list_agents
            break

    async def call_tool(name, args):
        return await server.call_tool(name, args)

    result = asyncio.run(call_tool("amf_list_agents", {"base_dir": str(base_dir)}))
    text = result[0][0].text
    parsed = json.loads(text)
    print(f"Final parsed result: {parsed}")
