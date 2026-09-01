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

    # Check state files on disk BEFORE create_mcp_server
    print(f"Before create_mcp_server:")
    print(f"  agents dir exists: {(base_dir / 'agents').exists()}")
    agents_dir = base_dir / "agents"
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            print(f"  agent dir: {agent_dir.name}")
            for f in agent_dir.iterdir():
                print(f"    file: {f.name} -> {f.read_text()[:200]}")

    print(f"  lifecycle._states: {lifecycle._states}")
    print(f"  lifecycle.list_agents(): {len(lifecycle.list_agents())} agents")

    # Now create MCP server
    server = create_mcp_server(base_dir=str(base_dir))

    # Check state files on disk AFTER create_mcp_server
    print(f"After create_mcp_server:")
    print(f"  agents dir exists: {(base_dir / 'agents').exists()}")
    agents_dir = base_dir / "agents"
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            print(f"  agent dir: {agent_dir.name}")
            for f in agent_dir.iterdir():
                print(f"    file: {f.name} -> {f.read_text()[:200]}")

    # Check if lifecycle still has the state
    lifecycle2 = AgentLifecycle(base_dir=base_dir)
    print(f"  new lifecycle._states: {lifecycle2._states}")
    print(f"  new lifecycle.list_agents(): {len(lifecycle2.list_agents())} agents")