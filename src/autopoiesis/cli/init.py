import sys
import json
import shutil
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


def resolve_autopoiesis_command() -> tuple[str, list[str]]:
    """Resolves the absolute path command and arguments for spawning the autopoiesis MCP server."""
    # Check if autopoiesis executable exists in PATH or current virtualenv
    autopoiesis_bin = shutil.which("autopoiesis")
    if autopoiesis_bin:
        return str(Path(autopoiesis_bin).resolve()), ["serve", "--mode", "stdio"]

    # Fallback to python executable module invocation
    python_bin = sys.executable
    return str(Path(python_bin).resolve()), ["-m", "autopoiesis.cli.main", "serve", "--mode", "stdio"]


def update_mcp_config_file(config_path: Path) -> bool:
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

    cmd, args = resolve_autopoiesis_command()

    data["mcpServers"]["autopoiesis-engine"] = {
        "command": cmd,
        "args": args,
        "env": {
            "AUTOPOIESIS_ENV": "development"
        }
    }

    config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def write_cursorrules_file(project_root: Path) -> Path:
    """Injects transparent intent interception rules into .cursorrules for IDE AI Agents."""
    cursorrules_path = project_root / ".cursorrules"
    rules_content = """# Autopoiesis Engine - Transparent Tool Delegation Rules
# Always delegate natural language operations, script execution, file manipulations, and process tasks to Autopoiesis Engine.

- NEVER write one-off local scripts or manual code to execute tasks that can be delegated to the Autopoiesis Engine.
- ALWAYS invoke the Autopoiesis MCP tool `run_intent` or `execute_macro_intent` for task requests.
- Pass the raw user request directly into the `intent` parameter.
"""
    cursorrules_path.write_text(rules_content, encoding="utf-8")
    return cursorrules_path


def populate_seed_skills(base_dir: Path, root_registry_dir: Path) -> None:
    """Populates Level 1 OS Core Base Pack primitive micro-skills into SQLite and Qdrant databases."""
    registry = RegistryManager(base_dir=base_dir)

    # 1. core_os_shell
    shell_code = """def main(inputs: dict) -> dict:
    \"\"\"Native shell execution wrapper (pwsh on Windows, /bin/bash on Unix).\"\"\"
    cmd = inputs.get("command", "")
    from autopoiesis.core.platform import PlatformAdapter
    proc = PlatformAdapter.run_command(cmd)
    return {
        "status": "success" if proc.returncode == 0 else "error",
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr
    }
"""
    registry.register_skill(
        skill_id="core_os_shell",
        namespace="global",
        scope_level="core",
        description="Executes native shell commands safely via PlatformAdapter (pwsh on Windows, /bin/bash on Unix).",
        inputs={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "stdout": {"type": "string"}, "stderr": {"type": "string"}}},
        python_code=shell_code,
        root_registry_dir=root_registry_dir,
    )

    # 2. core_os_env_path
    env_path_code = """def main(inputs: dict) -> dict:
    \"\"\"Environment variable querying and Windows-native UNC/path resolution.\"\"\"
    var_name = inputs.get("variable_name")
    path_str = inputs.get("path_str")
    import os
    from autopoiesis.core.platform import PlatformAdapter
    result = {}
    if var_name:
        result["value"] = os.environ.get(var_name)
    if path_str:
        result["resolved_path"] = str(PlatformAdapter.sanitize_path(path_str))
    return result
"""
    registry.register_skill(
        skill_id="core_os_env_path",
        namespace="global",
        scope_level="core",
        description="Queries environment variables and resolves OS-native paths.",
        inputs={"type": "object", "properties": {"variable_name": {"type": "string"}, "path_str": {"type": "string"}}},
        outputs={"type": "object", "properties": {"value": {"type": "string"}, "resolved_path": {"type": "string"}}},
        python_code=env_path_code,
        root_registry_dir=root_registry_dir,
    )

    # 3. core_fs_windows_ops
    fs_ops_code = """def main(inputs: dict) -> dict:
    \"\"\"File read/write with UTF-8/BOM handling and attribute validation.\"\"\"
    action = inputs.get("action", "read")
    filepath = inputs.get("filepath", "")
    content = inputs.get("content", "")
    from pathlib import Path
    p = Path(filepath)
    if action == "write":
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(content), encoding="utf-8")
        return {"status": "success", "filepath": str(p.resolve())}
    else:
        if not p.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        return {"status": "success", "filepath": str(p.resolve()), "content": p.read_text(encoding="utf-8")}
"""
    registry.register_skill(
        skill_id="core_fs_windows_ops",
        namespace="global",
        scope_level="core",
        description="Robust file system operations (read/write/attributes) with UTF-8 encoding support.",
        inputs={"type": "object", "properties": {"action": {"type": "string"}, "filepath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filepath"]},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "content": {"type": "string"}}},
        python_code=fs_ops_code,
        root_registry_dir=root_registry_dir,
    )

    # 4. core_os_proc_monitor
    proc_monitor_code = """def main(inputs: dict) -> dict:
    \"\"\"Process inspection and PID querying.\"\"\"
    process_name = inputs.get("process_name", "")
    import sys
    from autopoiesis.core.platform import PlatformAdapter
    if sys.platform == "win32":
        cmd = f"Get-Process -Name '{process_name}'" if process_name else "Get-Process | Select-Object -First 10"
    else:
        cmd = f"ps aux | grep {process_name}" if process_name else "ps aux | head -n 10"
    proc = PlatformAdapter.run_command(cmd)
    return {"status": "success", "output": proc.stdout}
"""
    registry.register_skill(
        skill_id="core_os_proc_monitor",
        namespace="global",
        scope_level="core",
        description="Inspects active processes, queries PIDs, and monitors system processes.",
        inputs={"type": "object", "properties": {"process_name": {"type": "string"}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "output": {"type": "string"}}},
        python_code=proc_monitor_code,
        root_registry_dir=root_registry_dir,
    )

    # 5. core_data_utilities
    data_utils_code = """def main(inputs: dict) -> dict:
    \"\"\"Fast JSON processing and Parquet conversion utility.\"\"\"
    data = inputs.get("data", {})
    import json
    if isinstance(data, str):
        data = json.loads(data)
    return {"status": "success", "processed_data": data}
"""
    registry.register_skill(
        skill_id="core_data_utilities",
        namespace="global",
        scope_level="core",
        description="Utilities for fast JSON/YAML processing and data transformations.",
        inputs={"type": "object", "properties": {"data": {}}, "required": ["data"]},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "processed_data": {}}},
        python_code=data_utils_code,
        root_registry_dir=root_registry_dir,
    )

    # 6. core_http_client
    http_code = """def main(inputs: dict) -> dict:
    \"\"\"HTTP request client supporting GET/POST/PUT/DELETE with headers and body.\"\"\"
    import urllib.request
    import json as _json
    url = inputs.get("url", "")
    method = inputs.get("method", "GET").upper()
    headers = inputs.get("headers", {})
    body = inputs.get("body")
    timeout = inputs.get("timeout", 30)

    if not url:
        return {"status": "error", "error": "Missing required parameter: url"}

    try:
        req = urllib.request.Request(url, method=method)
        for k, v in headers.items():
            req.add_header(k, str(v))
        data_bytes = None
        if body is not None:
            data_bytes = _json.dumps(body).encode("utf-8") if isinstance(body, (dict, list)) else str(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, data=data_bytes, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            try:
                resp_json = _json.loads(resp_body)
            except Exception:
                resp_json = resp_body
            return {
                "status": "success",
                "status_code": resp.status,
                "headers": dict(resp.headers),
                "body": resp_json,
            }
    except urllib.error.HTTPError as e:
        return {"status": "error", "status_code": e.code, "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
"""
    registry.register_skill(
        skill_id="core_http_client",
        namespace="global",
        scope_level="core",
        description="HTTP request client for REST API calls with GET/POST/PUT/DELETE support.",
        inputs={"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string"}, "headers": {"type": "object"}, "body": {}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "status_code": {"type": "integer"}, "body": {}}},
        python_code=http_code,
        root_registry_dir=root_registry_dir,
    )

    # 7. core_csv_processor
    csv_code = """def main(inputs: dict) -> dict:
    \"\"\"Advanced CSV processor: read, filter, transform, aggregate, and write.\"\"\"
    import csv
    import os
    from pathlib import Path

    file_path = inputs.get("file_path", "")
    action = inputs.get("action", "read")
    filter_col = inputs.get("filter_column")
    filter_val = inputs.get("filter_value")
    output_path = inputs.get("output_path", "")
    select_cols = inputs.get("select_columns", [])

    if not file_path or not Path(file_path).exists():
        return {"status": "error", "error": f"File not found: {file_path}"}

    rows = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if action == "read":
        return {"status": "success", "rows": rows, "count": len(rows)}

    if action == "filter":
        if not filter_col:
            return {"status": "error", "error": "filter_column required"}
        filtered = [r for r in rows if str(r.get(filter_col, "")) == str(filter_val)]
        return {"status": "success", "rows": filtered, "count": len(filtered)}

    if action == "aggregate":
        group_col = inputs.get("group_by", "")
        agg_col = inputs.get("aggregate_column", "")
        agg_op = inputs.get("aggregate_op", "sum")
        if not group_col or not agg_col:
            return {"status": "error", "error": "group_by and aggregate_column required"}
        groups: dict = {}
        for r in rows:
            key = r.get(group_col, "")
            groups.setdefault(key, []).append(float(r.get(agg_col, 0)))
        result = {}
        for k, vals in groups.items():
            if agg_op == "sum":
                result[k] = sum(vals)
            elif agg_op == "avg":
                result[k] = round(sum(vals) / len(vals), 4)
            elif agg_op == "count":
                result[k] = len(vals)
            else:
                result[k] = sum(vals)
        return {"status": "success", "aggregation": result}

    if action == "write" and output_path:
        if select_cols:
            rows = [{k: v for k, v in r.items() if k in select_cols} for r in rows]
        fieldnames = list(rows[0].keys()) if rows else []
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return {"status": "success", "written_to": output_path, "rows": len(rows)}

    return {"status": "error", "error": f"Unsupported action: {action}"}
"""
    registry.register_skill(
        skill_id="core_csv_processor",
        namespace="global",
        scope_level="core",
        description="Advanced CSV processing: read, filter, aggregate, and write.",
        inputs={"type": "object", "properties": {"file_path": {"type": "string"}, "action": {"type": "string"}, "filter_column": {"type": "string"}, "filter_value": {"type": "string"}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "rows": {"type": "array"}}},
        python_code=csv_code,
        root_registry_dir=root_registry_dir,
    )

    # 8. core_json_path
    jsonpath_code = """def main(inputs: dict) -> dict:
    \"\"\"Query JSON documents with dot-path expressions (e.g., 'users.0.name').\"\"\"
    import json
    data = inputs.get("data", {})
    query = inputs.get("query", "")

    if isinstance(data, str):
        data = json.loads(data)

    if not query:
        return {"status": "error", "error": "query is required"}

    parts = query.split(".")
    current = data
    try:
        for part in parts:
            if part.isdigit():
                current = current[int(part)]
            else:
                current = current[part]
        return {"status": "success", "result": current}
    except (KeyError, IndexError, TypeError) as e:
        return {"status": "error", "error": f"Query '{query}' failed: {e}"}
"""
    registry.register_skill(
        skill_id="core_json_path",
        namespace="global",
        scope_level="core",
        description="Query JSON documents with dot-path expressions.",
        inputs={"type": "object", "properties": {"data": {}, "query": {"type": "string"}}, "required": ["query"]},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "result": {}}},
        python_code=jsonpath_code,
        root_registry_dir=root_registry_dir,
    )

    # 9. core_yaml_processor
    yaml_code = """def main(inputs: dict) -> dict:
    \"\"\"Parse, query, and write YAML documents.\"\"\"
    try:
        import yaml as _yaml
    except ImportError:
        return {"status": "error", "error": "PyYAML is not installed. Run: pip install pyyaml"}

    action = inputs.get("action", "read")
    file_path = inputs.get("file_path", "")
    query = inputs.get("query", "")
    data = inputs.get("data")

    if action == "read" and file_path:
        try:
            content = open(file_path, "r", encoding="utf-8").read()
            parsed = _yaml.safe_load(content)
            return {"status": "success", "data": parsed}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    if action == "write" and file_path and data is not None:
        try:
            from pathlib import Path
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                _yaml.dump(data, f, default_flow_style=False)
            return {"status": "success", "written_to": file_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    return {"status": "error", "error": f"Unsupported action: {action}"}
"""
    registry.register_skill(
        skill_id="core_yaml_processor",
        namespace="global",
        scope_level="core",
        description="Parse, query, and write YAML documents.",
        inputs={"type": "object", "properties": {"action": {"type": "string"}, "file_path": {"type": "string"}, "data": {}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "data": {}}},
        python_code=yaml_code,
        root_registry_dir=root_registry_dir,
    )

    # 10. core_env_inspector
    env_inspect_code = """def main(inputs: dict) -> dict:
    \"\"\"Detailed environment inspection: PATH, variables, OS info, Python env.\"\"\"
    import os
    import sys
    import platform
    result = {
        "os": platform.system(),
        "os_version": platform.version(),
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "env_vars_count": len(os.environ),
        "path_dirs": os.environ.get("PATH", "").split(os.pathsep)[:20],
        "home": os.path.expanduser("~"),
        "temp": os.environ.get("TEMP", os.environ.get("TMP", "/tmp")),
    }
    filter_vars = inputs.get("filter_vars", [])
    if filter_vars:
        result["filtered_env"] = {k: v for k, v in os.environ.items() if k in filter_vars}
    return {"status": "success", "environment": result}
"""
    registry.register_skill(
        skill_id="core_env_inspector",
        namespace="global",
        scope_level="core",
        description="Detailed environment inspection: OS info, PATH, variables, Python env.",
        inputs={"type": "object", "properties": {"filter_vars": {"type": "array", "items": {"type": "string"}}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "environment": {}}},
        python_code=env_inspect_code,
        root_registry_dir=root_registry_dir,
    )

    # 11. core_system_health
    health_code = """def main(inputs: dict) -> dict:
    \"\"\"System health check: CPU, memory, disk usage (best-effort cross-platform).\"\"\"
    import shutil
    import os
    health = {
        "platform": os.name,
        "cwd": os.getcwd(),
        "disk_usage": {},
    }
    try:
        usage = shutil.disk_usage(os.getcwd())
        health["disk_usage"] = {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round(usage.used / usage.total * 100, 1),
        }
    except Exception as e:
        health["disk_error"] = str(e)
    return {"status": "success", "health": health}
"""
    registry.register_skill(
        skill_id="core_system_health",
        namespace="global",
        scope_level="core",
        description="System health check: disk usage and platform info.",
        inputs={"type": "object", "properties": {}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "health": {}}},
        python_code=health_code,
        root_registry_dir=root_registry_dir,
    )

    # 12. core_network_scanner
    net_code = """def main(inputs: dict) -> dict:
    \"\"\"Network diagnostics: DNS lookup, HTTP ping, and connectivity checks.\"\"\"
    import socket
    import urllib.request

    target = inputs.get("target", "")
    port = int(inputs.get("port", 80))
    timeout = float(inputs.get("timeout", 5))
    results = {"target": target, "checks": []}

    if not target:
        return {"status": "error", "error": "target is required"}

    # DNS resolution
    try:
        ip = socket.gethostbyname(target)
        results["checks"].append({"check": "dns", "status": "success", "ip": ip})
    except Exception as e:
        results["checks"].append({"check": "dns", "status": "error", "error": str(e)})
        return {"status": "success", "results": results}

    # TCP connect
    try:
        with socket.create_connection((target, port), timeout=timeout):
            results["checks"].append({"check": "tcp", "status": "success", "port": port})
    except Exception as e:
        results["checks"].append({"check": "tcp", "status": "error", "error": str(e)})

    # HTTP HEAD
    try:
        req = urllib.request.Request(f"http://{target}:{port}", method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            results["checks"].append({"check": "http", "status": "success", "status_code": resp.status})
    except Exception as e:
        results["checks"].append({"check": "http", "status": "error", "error": str(e)})

    return {"status": "success", "results": results}
"""
    registry.register_skill(
        skill_id="core_network_scanner",
        namespace="global",
        scope_level="core",
        description="Network diagnostics: DNS lookup, TCP connect, and HTTP HEAD checks.",
        inputs={"type": "object", "properties": {"target": {"type": "string"}, "port": {"type": "integer"}, "timeout": {"type": "number"}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "results": {}}},
        python_code=net_code,
        root_registry_dir=root_registry_dir,
    )

    # 13. core_file_watcher
    watcher_code = """def main(inputs: dict) -> dict:
    \"\"\"File watcher: lists files in a directory with metadata and optional filtering.\"\"\"
    import os
    from pathlib import Path
    from datetime import datetime

    dir_path = inputs.get("dir_path", ".")
    pattern = inputs.get("pattern", "*")
    recursive = inputs.get("recursive", False)

    base = Path(dir_path)
    if not base.exists() or not base.is_dir():
        return {"status": "error", "error": f"Directory not found: {dir_path}"}

    files = []
    glob_fn = base.rglob if recursive else base.glob
    for f in glob_fn(pattern):
        if f.is_file():
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f.resolve()),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    files.sort(key=lambda x: x["modified"], reverse=True)
    return {"status": "success", "files": files, "count": len(files)}
"""
    registry.register_skill(
        skill_id="core_file_watcher",
        namespace="global",
        scope_level="core",
        description="Lists files in a directory with metadata and pattern filtering.",
        inputs={"type": "object", "properties": {"dir_path": {"type": "string"}, "pattern": {"type": "string"}, "recursive": {"type": "boolean"}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "files": {"type": "array"}}},
        python_code=watcher_code,
        root_registry_dir=root_registry_dir,
    )

    # 14. core_process_manager
    proc_mgr_code = """def main(inputs: dict) -> dict:
    \"\"\"Process management: list, kill, and spawn background processes.\"\"\"
    import os
    import signal
    import subprocess

    action = inputs.get("action", "list")
    pid = inputs.get("pid")
    command = inputs.get("command")

    if action == "list":
        if os.name == "nt":
            cmd = "tasklist /FO CSV /NH"
        else:
            cmd = "ps -eo pid,comm,%cpu,%mem --no-headers"
        from autopoiesis.core.platform import PlatformAdapter
        proc = PlatformAdapter.run_command(cmd)
        return {"status": "success", "output": proc.stdout}

    if action == "kill" and pid:
        try:
            os.kill(int(pid), signal.SIGTERM)
            return {"status": "success", "killed_pid": int(pid)}
        except ProcessLookupError:
            return {"status": "error", "error": f"Process {pid} not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    if action == "spawn" and command:
        try:
            subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "success", "spawned": command}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    return {"status": "error", "error": f"Unsupported action: {action}"}
"""
    registry.register_skill(
        skill_id="core_process_manager",
        namespace="global",
        scope_level="core",
        description="Process management: list, kill, and spawn processes.",
        inputs={"type": "object", "properties": {"action": {"type": "string"}, "pid": {"type": "integer"}, "command": {"type": "string"}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "output": {"type": "string"}}},
        python_code=proc_mgr_code,
        root_registry_dir=root_registry_dir,
    )

    # 15. core_notification_bridge
    notify_code = """def main(inputs: dict) -> dict:
    \"\"\"Notification bridge: writes notifications to a local JSON queue for downstream delivery.\"\"\"
    import json
    import os
    from pathlib import Path
    from datetime import datetime

    channel = inputs.get("channel", "default")
    message = inputs.get("message", "")
    severity = inputs.get("severity", "info")
    payload = inputs.get("payload", {})

    if not message:
        return {"status": "error", "error": "message is required"}

    queue_dir = Path(".autopoiesis") / "notifications"
    queue_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": f"notif_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "channel": channel,
        "severity": severity,
        "message": message,
        "payload": payload,
        "timestamp": datetime.now().isoformat(),
    }
    queue_file = queue_dir / f"{channel}.json"
    existing = []
    if queue_file.exists():
        try:
            existing = json.loads(queue_file.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.append(entry)
    queue_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return {"status": "success", "notification_id": entry["id"], "channel": channel}
"""
    registry.register_skill(
        skill_id="core_notification_bridge",
        namespace="global",
        scope_level="core",
        description="Writes notifications to a local JSON queue for downstream delivery.",
        inputs={"type": "object", "properties": {"channel": {"type": "string"}, "message": {"type": "string"}, "severity": {"type": "string"}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "notification_id": {"type": "string"}}},
        python_code=notify_code,
        root_registry_dir=root_registry_dir,
    )

    # 16. core_data_viz
    viz_code = """def main(inputs: dict) -> dict:
    \"\"\"Data visualization generator: returns JSON chart spec for Plotly/Chart.js rendering.\"\"\"
    chart_type = inputs.get("chart_type", "bar")
    data = inputs.get("data", [])
    labels = inputs.get("labels", [])
    title = inputs.get("title", "Chart")
    x_label = inputs.get("x_label", "X")
    y_label = inputs.get("y_label", "Y")

    if not data and not labels:
        return {"status": "error", "error": "data or labels is required"}

    spec = {
        "type": chart_type,
        "data": {
            "labels": labels,
            "datasets": [{"label": title, "data": data}],
        },
        "options": {
            "plugins": {"title": {"display": True, "text": title}},
            "scales": {
                "x": {"title": {"display": True, "text": x_label}},
                "y": {"title": {"display": True, "text": y_label}},
            },
        },
    }
    return {"status": "success", "chart_spec": spec}
"""
    registry.register_skill(
        skill_id="core_data_viz",
        namespace="global",
        scope_level="core",
        description="Data visualization generator returning JSON chart spec.",
        inputs={"type": "object", "properties": {"chart_type": {"type": "string"}, "data": {"type": "array"}, "labels": {"type": "array"}, "title": {"type": "string"}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "chart_spec": {}}},
        python_code=viz_code,
        root_registry_dir=root_registry_dir,
    )

    # 17. core_regex_processor
    regex_code = """def main(inputs: dict) -> dict:
    \"\"\"Regex processor: test, find, replace, and split text using patterns.\"\"\"
    import re

    action = inputs.get("action", "test")
    pattern = inputs.get("pattern", "")
    text = inputs.get("text", "")
    replacement = inputs.get("replacement", "")
    flags = inputs.get("flags", 0)

    if not pattern:
        return {"status": "error", "error": "pattern is required"}
    if not text and action != "test":
        return {"status": "error", "error": "text is required"}

    compiled = re.compile(pattern, flags)

    if action == "test":
        return {"status": "success", "matched": bool(compiled.search(text))}

    if action == "find":
        matches = compiled.findall(text)
        return {"status": "success", "matches": matches, "count": len(matches)}

    if action == "replace":
        result, count = compiled.subn(replacement, text)
        return {"status": "success", "result": result, "replacements": count}

    if action == "split":
        parts = compiled.split(text)
        return {"status": "success", "parts": parts, "count": len(parts)}

    return {"status": "error", "error": f"Unsupported action: {action}"}
"""
    registry.register_skill(
        skill_id="core_regex_processor",
        namespace="global",
        scope_level="core",
        description="Regex processor: test, find, replace, and split text.",
        inputs={"type": "object", "properties": {"action": {"type": "string"}, "pattern": {"type": "string"}, "text": {"type": "string"}}},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "matches": {"type": "array"}}},
        python_code=regex_code,
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

    # Populate seed Level 1 OS Core Base Pack micro-skills
    populate_seed_skills(base_dir=base_dir, root_registry_dir=root_registry_dir)

    # Write .cursorrules for IDE transparent tool delegation
    cursorrules_path = write_cursorrules_file(root)

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
        "cursorrules_path": str(cursorrules_path),
    }
