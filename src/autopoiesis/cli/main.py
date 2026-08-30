import argparse
import sys
import shutil
from pathlib import Path
import uvicorn

from autopoiesis.cli.init import init_workspace, update_mcp_config_file, get_client_config_paths, PlatformAdapter
from autopoiesis.mcp.server import run_mcp_stdio_server, create_fastapi_app


def install_mcp_configs(target_path: str = ".") -> None:
    """Forces generation and overwriting of MCP config files in workspace and client paths."""
    root = PlatformAdapter.sanitize_path(target_path)
    print(f"Installing/Updating MCP configurations for workspace at {root}...")

    local_mcp_path = root / "mcp.json"
    update_mcp_config_file(local_mcp_path)
    print(f"Updated: {local_mcp_path}")

    client_paths = get_client_config_paths()
    for client, path in client_paths.items():
        try:
            update_mcp_config_file(path)
            print(f"Updated {client} config: {path}")
        except Exception as e:
            print(f"Could not update {client} config ({path}): {e}")

    print("MCP configuration update complete.")


def clean_workspace(target_path: str = ".") -> None:
    """Purges runtime state (.autopoiesis), workspace registry files, and mcp configs."""
    root = PlatformAdapter.sanitize_path(target_path)
    print(f"Cleaning workspace at {root}...")

    base_dir = root / ".autopoiesis"
    registry_dir = root / "registry"
    mcp_file = root / "mcp.json"
    rules_file = root / ".cursorrules"

    if base_dir.exists():
        shutil.rmtree(base_dir, ignore_errors=True)
        print("Purged .autopoiesis/ runtime directory.")

    if registry_dir.exists():
        shutil.rmtree(registry_dir, ignore_errors=True)
        print("Purged registry/ workspace directory.")

    if mcp_file.exists():
        mcp_file.unlink(missing_ok=True)
        print("Removed mcp.json file.")

    if rules_file.exists():
        rules_file.unlink(missing_ok=True)
        print("Removed .cursorrules file.")

    print("Workspace clean completed.")


def main():
    parser = argparse.ArgumentParser(description="Autopoiesis Engine CLI Tool")
    subparsers = parser.add_subparsers(dest="command")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize workspace and IDE MCP configurations.")
    init_parser.add_argument("--path", default=".", help="Project path to initialize.")

    # mcp-install command
    mcp_parser = subparsers.add_parser("mcp-install", help="Force overwrite MCP configuration files for IDEs.")
    mcp_parser.add_argument("--path", default=".", help="Project path to update.")

    # clean command
    clean_parser = subparsers.add_parser("clean", help="Purge runtime state (.autopoiesis) and legacy workspace files.")
    clean_parser.add_argument("--path", default=".", help="Project path to clean.")

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
    elif args.command == "mcp-install":
        install_mcp_configs(args.path)
    elif args.command == "clean":
        clean_workspace(args.path)
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
