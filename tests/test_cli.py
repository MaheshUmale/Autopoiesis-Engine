import pytest
from pathlib import Path
from autopoiesis.cli.init import init_workspace


def test_cli_init_workspace(tmp_path: Path):
    res = init_workspace(tmp_path)
    assert res["workspace_root"] == str(tmp_path.resolve())
    assert (tmp_path / "mcp.json").exists()
    assert (tmp_path / ".autopoiesis").exists()
    assert (tmp_path / "registry" / "level_1_core").exists()
    assert (tmp_path / "registry" / "level_2_variants").exists()
    assert (tmp_path / "registry" / "level_3_templates").exists()
