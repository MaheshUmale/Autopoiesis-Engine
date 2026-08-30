import pytest
from pathlib import Path

from autopoiesis.mcp.server import create_mcp_server, create_fastapi_app
from fastapi.testclient import TestClient


def test_mcp_fastapi_endpoints(tmp_path: Path):
    app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200

    ui_res = client.get("/ui")
    assert ui_res.status_code == 200
    assert "AUTOPOIESIS ENGINE" in ui_res.text

    dash_res = client.get("/dashboard")
    assert dash_res.status_code == 200

    tools_res = client.get("/tools")
    assert tools_res.status_code == 200
    assert isinstance(tools_res.json(), list)


def test_mcp_dashboard_api_endpoints(tmp_path: Path):
    app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
    client = TestClient(app)

    api_agents = client.get("/api/dashboard/agents")
    assert api_agents.status_code == 200
    data = api_agents.json()
    assert "stats" in data
    assert "agents" in data
    assert isinstance(data["agents"], list)

    api_logs = client.get("/api/dashboard/logs/global.parsers.json_parser")
    assert api_logs.status_code == 200
    log_data = api_logs.json()
    assert log_data["agent_id"] == "global.parsers.json_parser"
    assert "logs" in log_data


def test_mcp_resources_endpoints(tmp_path: Path):
    app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
    client = TestClient(app)

    reg_res = client.get("/resources/registry")
    assert reg_res.status_code == 200
    assert reg_res.json()["resource"] == "resource://autopoiesis/registry"

    cfg_res = client.get("/resources/config")
    assert cfg_res.status_code == 200
    assert cfg_res.json()["resource"] == "resource://autopoiesis/config"


def test_mcp_messages_endpoint(tmp_path: Path):
    app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
    client = TestClient(app)

    res = client.post("/messages", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert res.status_code == 200
    data = res.json()
    assert "result" in data
    assert "tools" in data["result"]


def test_mcp_server_instance(tmp_path: Path):
    server = create_mcp_server(base_dir=str(tmp_path / ".autopoiesis"))
    assert server is not None
