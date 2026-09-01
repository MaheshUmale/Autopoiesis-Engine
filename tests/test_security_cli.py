"""Security-focused tests for CLI init.

Validates config file manipulation, path handling, and injection prevention.
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from autopoiesis.cli.init import (
    get_client_config_paths,
    resolve_autopoiesis_command,
    update_mcp_config_file,
    write_cursorrules_file,
    init_workspace,
)


class TestGetClientConfigPaths:
    """Tests for client config path detection."""

    def test_returns_dict(self):
        """get_client_config_paths should return a dict."""
        paths = get_client_config_paths()
        assert isinstance(paths, dict)

    def test_contains_claude_path(self):
        """Should contain claude config path."""
        paths = get_client_config_paths()
        assert "claude" in paths

    def test_contains_cursor_path(self):
        """Should contain cursor config path."""
        paths = get_client_config_paths()
        assert "cursor" in paths

    def test_contains_vscode_path(self):
        """Should contain vscode config path."""
        paths = get_client_config_paths()
        assert "vscode" in paths

    def test_contains_kilocode_path(self):
        """Should contain kilocode config path."""
        paths = get_client_config_paths()
        assert "kilocode" in paths

    def test_claude_path_is_absolute(self):
        """Claude config path should be absolute."""
        paths = get_client_config_paths()
        assert paths["claude"].is_absolute()

    def test_paths_are_path_objects(self):
        """All paths should be Path objects."""
        paths = get_client_config_paths()
        for key, path in paths.items():
            assert isinstance(path, Path), f"{key} is not a Path object"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_claude_path(self):
        """On Windows, claude path should be in AppData."""
        paths = get_client_config_paths()
        assert "AppData" in str(paths["claude"]) or "claude_desktop_config" in str(paths["claude"])

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
    def test_unix_claude_path(self):
        """On Unix, claude path should be in .config or Library."""
        paths = get_client_config_paths()
        path_str = str(paths["claude"])
        assert ".config" in path_str or "Library" in path_str


class TestResolveAutopoiesisCommand:
    """Tests for autopoiesis command resolution."""

    def test_returns_tuple(self):
        """resolve_autopoiesis_command should return a tuple."""
        result = resolve_autopoiesis_command()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_command_is_string(self):
        """Command should be a string."""
        cmd, args = resolve_autopoiesis_command()
        assert isinstance(cmd, str)

    def test_args_is_list(self):
        """Args should be a list."""
        cmd, args = resolve_autopoiesis_command()
        assert isinstance(args, list)

    def test_contains_serve_mode(self):
        """Args should contain serve mode."""
        cmd, args = resolve_autopoiesis_command()
        assert "--mode" in args
        assert "stdio" in args


class TestUpdateMcpConfigFile:
    """Tests for MCP config file manipulation."""

    def test_creates_new_config(self, tmp_path):
        """Should create new config file if it doesn't exist."""
        config_path = tmp_path / "mcp.json"
        result = update_mcp_config_file(config_path)
        assert result is True
        assert config_path.exists()

    def test_creates_parent_directories(self, tmp_path):
        """Should create parent directories if needed."""
        config_path = tmp_path / "subdir" / "mcp.json"
        result = update_mcp_config_file(config_path)
        assert result is True
        assert config_path.exists()

    def test_contains_mcp_servers(self, tmp_path):
        """Config should contain mcpServers key."""
        config_path = tmp_path / "mcp.json"
        update_mcp_config_file(config_path)
        data = json.loads(config_path.read_text())
        assert "mcpServers" in data

    def test_contains_autopoiesis_entry(self, tmp_path):
        """Config should contain autopoiesis-engine entry."""
        config_path = tmp_path / "mcp.json"
        update_mcp_config_file(config_path)
        data = json.loads(config_path.read_text())
        assert "autopoiesis-engine" in data["mcpServers"]

    def test_preserves_existing_config(self, tmp_path):
        """Should preserve existing config entries."""
        config_path = tmp_path / "mcp.json"
        existing_data = {
            "mcpServers": {
                "other-server": {
                    "command": "other",
                    "args": ["--serve"]
                }
            }
        }
        config_path.write_text(json.dumps(existing_data))

        update_mcp_config_file(config_path)
        data = json.loads(config_path.read_text())
        assert "other-server" in data["mcpServers"]
        assert "autopoiesis-engine" in data["mcpServers"]

    def test_handles_corrupted_config(self, tmp_path):
        """Should handle corrupted config file gracefully."""
        config_path = tmp_path / "mcp.json"
        config_path.write_text("not valid json {{{")

        result = update_mcp_config_file(config_path)
        assert result is True
        data = json.loads(config_path.read_text())
        assert "autopoiesis-engine" in data["mcpServers"]

    def test_config_is_valid_json(self, tmp_path):
        """Config file should be valid JSON."""
        config_path = tmp_path / "mcp.json"
        update_mcp_config_file(config_path)
        content = config_path.read_text()
        # Should not raise
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_env_contains_autopoiesis_env(self, tmp_path):
        """Config env should contain AUTOPOIESIS_ENV."""
        config_path = tmp_path / "mcp.json"
        update_mcp_config_file(config_path)
        data = json.loads(config_path.read_text())
        env = data["mcpServers"]["autopoiesis-engine"]["env"]
        assert "AUTOPOIESIS_ENV" in env


class TestWriteCursorrulesFile:
    """Tests for .cursorrules file creation."""

    def test_creates_file(self, tmp_path):
        """Should create .cursorrules file."""
        result = write_cursorrules_file(tmp_path)
        assert result.exists()

    def test_file_name_is_cursorrules(self, tmp_path):
        """File should be named .cursorrules."""
        result = write_cursorrules_file(tmp_path)
        assert result.name == ".cursorrules"

    def test_contains_delegation_rules(self, tmp_path):
        """File should contain delegation rules."""
        result = write_cursorrules_file(tmp_path)
        content = result.read_text()
        assert "delegation" in content.lower() or "delegate" in content.lower()

    def test_contains_run_intent_reference(self, tmp_path):
        """File should reference run_intent tool."""
        result = write_cursorrules_file(tmp_path)
        content = result.read_text()
        assert "run_intent" in content or "execute_macro_intent" in content


class TestInitWorkspace:
    """Tests for workspace initialization."""

    def test_creates_directory_structure(self, tmp_path):
        """Should create required directory structure."""
        result = init_workspace(tmp_path)
        assert (tmp_path / ".autopoiesis").exists()
        assert (tmp_path / "registry" / "level_1_core").exists()
        assert (tmp_path / "registry" / "level_2_variants").exists()
        assert (tmp_path / "registry" / "level_3_templates").exists()

    def test_creates_mcp_config(self, tmp_path):
        """Should create mcp.json config."""
        init_workspace(tmp_path)
        assert (tmp_path / "mcp.json").exists()

    def test_creates_cursorrules(self, tmp_path):
        """Should create .cursorrules file."""
        init_workspace(tmp_path)
        assert (tmp_path / ".cursorrules").exists()

    def test_returns_workspace_root(self, tmp_path):
        """Should return workspace root in result."""
        result = init_workspace(tmp_path)
        assert result["workspace_root"] == str(tmp_path.resolve())

    def test_returns_configured_clients(self, tmp_path):
        """Should return list of configured clients."""
        result = init_workspace(tmp_path)
        assert "configured_clients" in result
        assert isinstance(result["configured_clients"], list)

    def test_mcp_config_is_valid(self, tmp_path):
        """Generated mcp.json should be valid."""
        init_workspace(tmp_path)
        config_path = tmp_path / "mcp.json"
        data = json.loads(config_path.read_text())
        assert "mcpServers" in data

    def test_idempotent_execution(self, tmp_path):
        """Running init twice should not fail."""
        init_workspace(tmp_path)
        result = init_workspace(tmp_path)
        assert result["workspace_root"] == str(tmp_path.resolve())

    def test_handles_existing_files(self, tmp_path):
        """Should handle existing files gracefully."""
        # Pre-create some files
        (tmp_path / ".autopoiesis").mkdir()
        (tmp_path / "mcp.json").write_text('{"existing": true}')

        result = init_workspace(tmp_path)
        assert result["workspace_root"] == str(tmp_path.resolve())
