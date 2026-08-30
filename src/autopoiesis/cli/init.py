import sys
import json
from pathlib import Path
from typing import Dict, Any

from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.registry.manager import RegistryManager


def get_client_config_paths() -> Dict[str, Path]:
    """Detects home directory and returns config paths for supported IDEs/clients."""
    home = Path.home()
    paths = {}

    if sys.platform == "darwin":
        paths["claude"] = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "win32":
        paths["claude"] = home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    else:
        paths["claude"] = home / ".config" / "Claude" / "claude_desktop_config.json"

    paths["cursor"] = Path(".cursor") / "mcp.json"
    paths["vscode"] = Path(".vscode") / "mcp.json"
    paths["kilocode"] = Path(".kilocode") / "mcp.json"

    return paths


def update_mcp_config_file(config_path: Path, server_cmd: str = "autopoiesis") -> bool:
    """Injects or updates the autopoiesis-engine entry in an mcp.json or claude_desktop_config.json file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}

    data["mcpServers"]["autopoiesis-engine"] = {
        "command": server_cmd,
        "args": ["serve", "--mode", "stdio"],
        "env": {
            "AUTOPOIESIS_ENV": "development"
        }
    }

    config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def populate_seed_skills(base_dir: Path, root_registry_dir: Path) -> None:
    """Populates Level 1 Core primitive micro-skills into SQLite and Qdrant databases."""
    registry = RegistryManager(base_dir=base_dir)

    # Seed 1: JSON Transformer & Double Parser
    json_parser_code = """def main(inputs: dict) -> dict:
    \"\"\"Parses JSON input data and doubles the value field.\"\"\"
    data = inputs.get("data", {})
    if isinstance(data, str):
        import json
        data = json.loads(data)
    val = data.get("value", inputs.get("value", 0))
    return {"status": "success", "original_value": val, "doubled_value": val * 2}
"""
    registry.register_skill(
        skill_id="global.parsers.json_parser",
        namespace="global",
        scope_level="core",
        description="Parses JSON payload data and doubles numerical value fields.",
        inputs={"type": "object", "properties": {"value": {"type": "number"}, "data": {"type": "object"}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "doubled_value": {"type": "number"}}},
        python_code=json_parser_code,
        root_registry_dir=root_registry_dir,
    )

    # Seed 2: Generic File Writer
    file_writer_code = """def main(inputs: dict) -> dict:
    \"\"\"Writes text or JSON content to a specified filepath.\"\"\"
    filepath = inputs.get("filepath", "output.json")
    content = inputs.get("content", "")
    import json
    from pathlib import Path
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, (dict, list)):
        p.write_text(json.dumps(content, indent=2), encoding="utf-8")
    else:
        p.write_text(str(content), encoding="utf-8")
    return {"status": "success", "filepath": str(p.resolve())}
"""
    registry.register_skill(
        skill_id="global.file.writer",
        namespace="global",
        scope_level="core",
        description="Writes content or JSON data to a destination file path.",
        inputs={"type": "object", "properties": {"filepath": {"type": "string"}, "content": {}}, "required": ["filepath", "content"]},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "filepath": {"type": "string"}}},
        python_code=file_writer_code,
        root_registry_dir=root_registry_dir,
    )


def init_workspace(project_dir: str | Path = ".") -> Dict[str, Any]:
    """Initializes workspace structure and generates valid mcp.json configurations."""
    root = PlatformAdapter.sanitize_path(project_dir)

    # Create required directory structure
    base_dir = root / ".autopoiesis"
    root_registry_dir = root / "registry"

    base_dir.mkdir(parents=True, exist_ok=True)
    (root_registry_dir / "level_1_core").mkdir(parents=True, exist_ok=True)
    (root_registry_dir / "level_2_variants").mkdir(parents=True, exist_ok=True)
    (root_registry_dir / "level_3_templates").mkdir(parents=True, exist_ok=True)

    # Populate seed Level 1 Core primitive micro-skills
    populate_seed_skills(base_dir=base_dir, root_registry_dir=root_registry_dir)

    # Inject mcp configuration into local .mcp.json and client paths
    local_mcp_path = root / "mcp.json"
    update_mcp_config_file(local_mcp_path)

    client_paths = get_client_config_paths()
    configured_clients = ["local_mcp.json"]

    for client, path in client_paths.items():
        try:
            update_mcp_config_file(path)
            configured_clients.append(client)
        except Exception:
            pass

    return {
        "workspace_root": str(root),
        "configured_clients": configured_clients,
        "mcp_config_path": str(local_mcp_path),
    }
