import tempfile
from pathlib import Path

from autopoiesis.registry.manager import RegistryManager
from autopoiesis.amf.registry import AMFRegistry
from autopoiesis.amf.schema import AgentDef, Capability
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

    print(f"Before create_mcp_server:")
    skill = reg.get_skill("test.echo")
    print(f"  get_skill('test.echo'): {skill is not None}")
    print(f"  base_dir contents: {list(base_dir.iterdir())}")
    
    # Create MCP server
    server = create_mcp_server(base_dir=str(base_dir))
    
    print(f"After create_mcp_server:")
    print(f"  base_dir contents: {list(base_dir.iterdir())}")
    
    # Check nested .autopoiesis
    nested = base_dir / ".autopoiesis"
    print(f"  nested .autopoiesis exists: {nested.exists()}")
    if nested.exists():
        print(f"  nested contents: {list(nested.iterdir())}")
    
    # Check if skill is still findable
    reg2 = RegistryManager(base_dir=base_dir)
    skill2 = reg2.get_skill("test.echo")
    print(f"  get_skill('test.echo') after: {skill2 is not None}")
    
    # Check DB files
    db1 = base_dir / "autopoiesis.db"
    db2 = nested / "autopoiesis.db" if nested.exists() else None
    print(f"  db1 exists: {db1.exists()}")
    print(f"  db2 exists: {db2.exists() if db2 else 'N/A'}")
