import pytest
from pathlib import Path

from autopoiesis.mcp.server import create_mcp_server, create_fastapi_app
from fastapi.testclient import TestClient


def test_mcp_fastapi_endpoints(tmp_path: Path):
    app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "list_tools" in data["endpoints"]

    tools_res = client.get("/tools")
    assert tools_res.status_code == 200
    assert isinstance(tools_res.json(), list)


def test_mcp_server_instance(tmp_path: Path):
    server = create_mcp_server(base_dir=str(tmp_path / ".autopoiesis"))
    assert server is not None
