import sys
import json
from pathlib import Path
from typing import Dict, Any

from autopoiesis.core.platform import PlatformAdapter


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


def init_workspace(project_dir: str | Path = ".") -> Dict[str, Any]:
    """Initializes workspace structure and generates valid mcp.json configurations."""
    root = PlatformAdapter.sanitize_path(project_dir)

    # Create required directory structure
    (root / ".autopoiesis").mkdir(parents=True, exist_ok=True)
    (root / "registry" / "level_1_core").mkdir(parents=True, exist_ok=True)
    (root / "registry" / "level_2_variants").mkdir(parents=True, exist_ok=True)
    (root / "registry" / "level_3_templates").mkdir(parents=True, exist_ok=True)

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
