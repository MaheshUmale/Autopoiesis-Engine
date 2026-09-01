import asyncio
import json
import tempfile
from pathlib import Path

from autopoiesis.mcp.server import create_mcp_server

with tempfile.TemporaryDirectory() as tmp_path:
    tmp_path = Path(tmp_path)
    base_dir = tmp_path / ".autopoiesis"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "registry").mkdir(parents=True, exist_ok=True)

    server = create_mcp_server(base_dir=str(base_dir))

    tm = server._tool_manager
    print(f"ToolManager type: {type(tm)}")
    print(f"ToolManager dir: {[a for a in dir(tm) if not a.startswith('_')]}")
    
    if hasattr(tm, '_tools'):
        print(f"_tools keys: {list(tm._tools.keys())}")
        tool = tm._tools.get('amf_list_agents')
        if tool:
            print(f"amf_list_agents tool: {tool}")
            print(f"tool type: {type(tool)}")
            print(f"tool dir: {[a for a in dir(tool) if not a.startswith('_')]}")
            if hasattr(tool, 'fn'):
                print(f"tool.fn: {tool.fn}")
                print(f"tool.fn signature: {tool.fn.__code__.co_varnames[:tool.fn.__code__.co_argcount]}")
            if hasattr(tool, 'parameters'):
                print(f"tool.parameters: {tool.parameters}")
