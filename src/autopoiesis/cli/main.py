import argparse
import sys
import uvicorn

from autopoiesis.cli.init import init_workspace
from autopoiesis.mcp.server import run_mcp_stdio_server, create_fastapi_app


def main():
    parser = argparse.ArgumentParser(description="Autopoiesis Engine CLI Tool")
    subparsers = parser.add_subparsers(dest="command")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize workspace and IDE MCP configurations.")
    init_parser.add_argument("--path", default=".", help="Project path to initialize.")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Run the MCP server daemon.")
    serve_parser.add_argument("--mode", choices=["stdio", "http"], default="stdio", help="Transport mode.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP mode.")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port for HTTP mode.")

    args = parser.parse_args()

    if args.command == "init":
        res = init_workspace(args.path)
        print(f"Workspace initialized successfully at {res['workspace_root']}")
        print(f"Configured MCP clients: {', '.join(res['configured_clients'])}")
        print(f"Generated MCP config: {res['mcp_config_path']}")
    elif args.command == "serve":
        if args.mode == "stdio":
            import asyncio
            asyncio.run(run_mcp_stdio_server())
        else:
            app = create_fastapi_app()
            uvicorn.run(app, host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
