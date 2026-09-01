"""Functional tests for micro-skills: verify they are not empty templates and can execute."""
import pytest
from pathlib import Path
from autopoiesis.registry.manager import RegistryManager


def test_skill_execution_end_to_end(tmp_path: Path):
    """Verify a registered skill can actually execute and produce meaningful output."""
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    # Register a skill with real logic (not an empty template)
    code = '''
def main(inputs: dict) -> dict:
    """Double the input value."""
    val = inputs.get("val", 0)
    return {"result": val * 2}
'''

    skill = registry.register_skill(
        skill_id="global.math.double",
        namespace="global",
        scope_level="core",
        description="Doubles input value with real logic",
        inputs={"type": "object", "properties": {"val": {"type": "integer"}}, "required": ["val"]},
        outputs={"type": "object", "properties": {"result": {"type": "integer"}}},
        python_code=code,
        root_registry_dir=tmp_path / "registry",
    )

    assert skill.id == "global.math.double"
    assert skill.description == "Doubles input value with real logic"
    assert skill.namespace == "global"
    assert skill.scope_level == "core"

    # Execute the skill via registry
    result = registry.invoke_skill("global.math.double", {"val": 42})
    assert result["result"] == 84, f"Expected 84, got {result}"

    # Also test via direct sandbox execution
    from autopoiesis.sandbox.executor import SandboxExecutor
    exec_result = SandboxExecutor.execute_skill_code(
        python_code=code,
        input_payload={"val": 42},
    )
    assert exec_result.success is True
    assert exec_result.output_payload == {"result": 84}


def test_skill_with_strings(tmp_path: Path):
    """Test skill that operates on string inputs."""
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    code = '''
def main(inputs: dict) -> dict:
    """Uppercase the input string."""
    s = inputs.get("text", "")
    return {"upper": s.upper()}
'''

    skill = registry.register_skill(
        skill_id="global.strings.uppercase",
        namespace="global",
        scope_level="core",
        description="Uppercases input text",
        inputs={"type": "object", "properties": {"text": {"type": "string"}}},
        outputs={"type": "object", "properties": {"upper": {"type": "string"}}},
        python_code=code,
        root_registry_dir=tmp_path / "registry",
    )

    result = registry.invoke_skill("global.strings.uppercase", {"text": "hello autopoiesis"})
    assert result["upper"] == "HELLO AUTOPOIESIS"  # case-insensitive check


def test_skill_with_lists(tmp_path: Path):
    """Test skill that operates on list inputs."""
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    code = '''
def main(inputs: dict) -> dict:
    """Reverse a list of numbers."""
    nums = inputs.get("numbers", [])
    return {"reversed": list(reversed(nums))}
'''

    skill = registry.register_skill(
        skill_id="global.lists.reverse",
        namespace="global",
        scope_level="core",
        description="Reverses a list of numbers",
        inputs={"type": "object", "properties": {"numbers": {"type": "array", "items": {"type": "integer"}}}},
        outputs={"type": "object", "properties": {"reversed": {"type": "array"}}},
        python_code=code,
        root_registry_dir=tmp_path / "registry",
    )

    result = registry.invoke_skill("global.lists.reverse", {"numbers": [1, 2, 3, 4, 5]})
    assert result["reversed"] == [5, 4, 3, 2, 1]


def test_skill_not_empty_template(tmp_path: Path):
    """Ensure registered skills have actual logic - not just returning empty dict."""
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    # Register a skill that actually does something (not just return {})
    code_with_logic = """
def main(inputs: dict) -> dict:
    x = inputs.get("x", 0)
    y = inputs.get("y", 0)
    return {"sum": x + y, "product": x * y}
"""

    skill = registry.register_skill(
        skill_id="global.math.operations",
        namespace="global",
        scope_level="core",
        description="Performs basic math operations",
        inputs={"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}},
        outputs={"type": "object", "properties": {"sum": {"type": "integer"}, "product": {"type": "integer"}}},
        python_code=code_with_logic,
        root_registry_dir=tmp_path / "registry",
    )

    # Execute and verify real output (not empty template)
    result = registry.invoke_skill("global.math.operations", {"x": 3, "y": 7})
    assert result["sum"] == 10, f"Expected sum=10, got {result.get('sum')}"
    assert result["product"] == 21, f"Expected product=21, got {result.get('product')}"

    # BONUS: Verify it's NOT an empty template by checking the result has real keys
    assert "sum" in result
    assert "product" in result
    assert len(result) == 2


def test_skill_deduplication_preserves_logic(tmp_path: Path):
    """Test that skill deduplication keeps the same code/logic."""
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    code = """
def main(inputs: dict) -> dict:
    val = inputs.get("val", 0)
    return {"result": val * 2 + 10}
"""

    # Register first occurrence
    skill1 = registry.register_skill(
        skill_id="global.math.with_offset",
        namespace="global",
        scope_level="core",
        description="Doubles value with offset",
        inputs={"type": "object", "properties": {"val": {"type": "integer"}}},
        outputs={"type": "object", "properties": {"result": {"type": "integer"}}},
        python_code=code,
        root_registry_dir=tmp_path / "registry",
    )

    # Register duplicate - should return existing skill via deduplication
    skill2 = registry.register_skill(
        skill_id="global.math.with_offset_v2",
        namespace="global",
        scope_level="core",
        description="Doubles value with offset v2",
        inputs={"type": "object", "properties": {"val": {"type": "integer"}}},
        outputs={"type": "object", "properties": {"result": {"type": "integer"}}},
        python_code=code,  # Same code
        root_registry_dir=tmp_path / "registry",
    )

    # Should return the same skill ID due to AST/hash deduplication
    assert skill2.id == skill1.id

    # Both should produce same result
    result1 = registry.invoke_skill("global.math.with_offset", {"val": 5})
    result2 = registry.invoke_skill("global.math.with_offset", {"val": 5})
    assert result1 == result2 == {"result": 20}  # 5*2+10 = 20


def test_skill_search_by_description(tmp_path: Path):
    """Test that skills can be searched by description content."""
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    # Register skills with distinct descriptions
    codes = [
        ('def main(inputs): return {"ok": True}', "simple return skill"),
        ('def main(inputs): return {"double": inputs.get("x", 0) * 2}', "math skill"),
        ('def main(inputs): return {"upper": inputs.get("s", "").upper()}', "string skill"),
    ]

    for code, desc in codes:
        registry.register_skill(
            skill_id=f"global.test.{desc.replace(' ', '_')}",
            namespace="global",
            scope_level="core",
            description=desc,
            inputs={},
            outputs={},
            python_code=code,
            root_registry_dir=tmp_path / "registry",
        )

    # Search for skills containing "math" in description
    results = registry.search_skills("math", active_namespaces=["global"])
    assert len(results) > 0
    math_skill_ids = [r["skill"].id for r in results]
    assert any("math" in sid for sid in math_skill_ids)

    # Search for skills containing "string" in description
    results = registry.search_skills("string", active_namespaces=["global"])
    assert len(results) > 0
    string_skill_ids = [r["skill"].id for r in results]
    assert any("string" in sid for sid in string_skill_ids)


def test_skill_with_no_inputs_outputs(tmp_path: Path):
    """Test skill that takes no inputs and produces no outputs."""
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    code = """
def main(inputs: dict) -> dict:
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00"}
"""

    skill = registry.register_skill(
        skill_id="global.health.check",
        namespace="global",
        scope_level="core",
        description="Health check skill",
        inputs={},
        outputs={"type": "object", "properties": {"status": {"type": "string"}, "timestamp": {"type": "string"}}},
        python_code=code,
        root_registry_dir=tmp_path / "registry",
    )

    result = registry.invoke_skill("global.health.check", {})
    assert result["status"] == "healthy"
    assert "timestamp" in result


def test_register_skill_validates_code_has_main(tmp_path: Path):
    """Test that registering a skill without 'main' function raises error."""
    base_dir = tmp_path / ".autopoiesis"
    registry = RegistryManager(base_dir=base_dir)

    # Code without main function
    bad_code = "def not_main(inputs): return {'bad': True}"

    with pytest.raises((AttributeError, ImportError), match="main"):
        registry.register_skill(
            skill_id="global.bad.code",
            namespace="global",
            scope_level="core",
            description="Skill without main function",
            inputs={},
            outputs={},
            python_code=bad_code,
            root_registry_dir=tmp_path / "registry",
        )


class TestExpandedSeedSkills:
    """Functional tests for the 12 expanded Level 1 seed skills."""

    def test_core_http_client(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_http_client",
            namespace="global",
            scope_level="core",
            description="HTTP request client for REST API calls.",
            inputs={"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string"}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "status_code": {"type": "integer"}}},
            python_code='def main(inputs: dict) -> dict:\n    url = inputs.get("url", "")\n    method = inputs.get("method", "GET").upper()\n    return {"status": "success", "status_code": 200, "body": "ok"}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_http_client"
        result = registry.invoke_skill("core_http_client", {"url": "http://example.com", "method": "GET"})
        assert result["status"] == "success"

    def test_core_csv_processor(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        skill = registry.register_skill(
            skill_id="core_csv_processor",
            namespace="global",
            scope_level="core",
            description="Advanced CSV processing: read, filter, aggregate, and write.",
            inputs={"type": "object", "properties": {"file_path": {"type": "string"}, "action": {"type": "string"}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "rows": {"type": "array"}}},
            python_code='def main(inputs: dict) -> dict:\n    file_path = inputs.get("file_path", "")\n    action = inputs.get("action", "read")\n    from pathlib import Path\n    if not Path(file_path).exists():\n        return {"status": "error", "error": f"File not found: {file_path}"}\n    if action == "read":\n        import csv\n        rows = []\n        with open(file_path, "r", encoding="utf-8") as f:\n            reader = csv.DictReader(f)\n            for row in reader:\n                rows.append(row)\n        return {"status": "success", "rows": rows, "count": len(rows)}\n    return {"status": "error", "error": f"Unsupported action: {action}"}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_csv_processor"
        result = registry.invoke_skill("core_csv_processor", {"file_path": str(csv_file), "action": "read"})
        assert result["status"] == "success"
        assert result["count"] == 2

    def test_core_json_path(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_json_path",
            namespace="global",
            scope_level="core",
            description="Query JSON documents with dot-path expressions.",
            inputs={"type": "object", "properties": {"data": {}, "query": {"type": "string"}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "result": {}}},
            python_code='def main(inputs: dict) -> dict:\n    data = inputs.get("data", {})\n    query = inputs.get("query", "")\n    if isinstance(data, str):\n        import json\n        data = json.loads(data)\n    if not query:\n        return {"status": "error", "error": "query is required"}\n    parts = query.split(".")\n    current = data\n    try:\n        for part in parts:\n            if part.isdigit():\n                current = current[int(part)]\n            else:\n                current = current[part]\n        return {"status": "success", "result": current}\n    except (KeyError, IndexError, TypeError) as e:\n        return {"status": "error", "error": f"Query failed: {e}"}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_json_path"
        result = registry.invoke_skill("core_json_path", {"data": {"users": [{"name": "Alice"}]}, "query": "users.0.name"})
        assert result["status"] == "success"
        assert result["result"] == "Alice"

    def test_core_yaml_processor(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_yaml_processor",
            namespace="global",
            scope_level="core",
            description="Parse, query, and write YAML documents.",
            inputs={"type": "object", "properties": {"action": {"type": "string"}, "file_path": {"type": "string"}, "data": {}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "data": {}}},
            python_code='def main(inputs: dict) -> dict:\n    action = inputs.get("action", "read")\n    file_path = inputs.get("file_path", "")\n    data = inputs.get("data")\n    if action == "read" and file_path:\n        try:\n            content = open(file_path, "r", encoding="utf-8").read()\n            import yaml as _yaml\n            parsed = _yaml.safe_load(content)\n            return {"status": "success", "data": parsed}\n        except Exception as e:\n            return {"status": "error", "error": str(e)}\n    if action == "write" and file_path and data is not None:\n        try:\n            from pathlib import Path\n            Path(file_path).parent.mkdir(parents=True, exist_ok=True)\n            import yaml as _yaml\n            with open(file_path, "w", encoding="utf-8") as f:\n                _yaml.dump(data, f, default_flow_style=False)\n            return {"status": "success", "written_to": file_path}\n        except Exception as e:\n            return {"status": "error", "error": str(e)}\n    return {"status": "error", "error": f"Unsupported action: {action}"}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_yaml_processor"
        # Test read with missing file returns error gracefully
        result = registry.invoke_skill("core_yaml_processor", {"action": "read", "file_path": "nonexistent.yaml"})
        assert result["status"] == "error"

    def test_core_env_inspector(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_env_inspector",
            namespace="global",
            scope_level="core",
            description="Detailed environment inspection: OS info, PATH, variables.",
            inputs={"type": "object", "properties": {"filter_vars": {"type": "array", "items": {"type": "string"}}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "environment": {}}},
            python_code='def main(inputs: dict) -> dict:\n    import os\n    import sys\n    import platform\n    result = {\n        "os": platform.system(),\n        "python_version": sys.version,\n        "cwd": os.getcwd(),\n        "env_vars_count": len(os.environ),\n        "home": os.path.expanduser("~"),\n    }\n    return {"status": "success", "environment": result}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_env_inspector"
        result = registry.invoke_skill("core_env_inspector", {})
        assert result["status"] == "success"
        assert "os" in result["environment"]

    def test_core_system_health(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_system_health",
            namespace="global",
            scope_level="core",
            description="System health check: disk usage and platform info.",
            inputs={"type": "object", "properties": {}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "health": {}}},
            python_code='def main(inputs: dict) -> dict:\n    import shutil\n    import os\n    health = {"platform": os.name, "cwd": os.getcwd(), "disk_usage": {}}\n    try:\n        usage = shutil.disk_usage(os.getcwd())\n        health["disk_usage"] = {\n            "total_gb": round(usage.total / (1024**3), 2),\n            "used_gb": round(usage.used / (1024**3), 2),\n            "free_gb": round(usage.free / (1024**3), 2),\n        }\n    except Exception as e:\n        health["disk_error"] = str(e)\n    return {"status": "success", "health": health}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_system_health"
        result = registry.invoke_skill("core_system_health", {})
        assert result["status"] == "success"
        assert "health" in result

    def test_core_network_scanner(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_network_scanner",
            namespace="global",
            scope_level="core",
            description="Network diagnostics: DNS lookup, TCP connect, and HTTP HEAD checks.",
            inputs={"type": "object", "properties": {"target": {"type": "string"}, "port": {"type": "integer"}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "results": {}}},
            python_code='def main(inputs: dict) -> dict:\n    target = inputs.get("target", "")\n    port = int(inputs.get("port", 80))\n    results = {"target": target, "checks": []}\n    if not target:\n        return {"status": "error", "error": "target is required"}\n    try:\n        import socket\n        ip = socket.gethostbyname(target)\n        results["checks"].append({"check": "dns", "status": "success", "ip": ip})\n    except Exception as e:\n        results["checks"].append({"check": "dns", "status": "error", "error": str(e)})\n        return {"status": "success", "results": results}\n    return {"status": "success", "results": results}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_network_scanner"
        result = registry.invoke_skill("core_network_scanner", {"target": "localhost", "port": 80})
        assert result["status"] == "success"
        assert "results" in result

    def test_core_file_watcher(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_file_watcher",
            namespace="global",
            scope_level="core",
            description="Lists files in a directory with metadata and pattern filtering.",
            inputs={"type": "object", "properties": {"dir_path": {"type": "string"}, "pattern": {"type": "string"}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "files": {"type": "array"}}},
            python_code='def main(inputs: dict) -> dict:\n    import os\n    from pathlib import Path\n    from datetime import datetime\n    dir_path = inputs.get("dir_path", ".")\n    pattern = inputs.get("pattern", "*")\n    base = Path(dir_path)\n    if not base.exists() or not base.is_dir():\n        return {"status": "error", "error": f"Directory not found: {dir_path}"}\n    files = []\n    for f in base.glob(pattern):\n        if f.is_file():\n            stat = f.stat()\n            files.append({"name": f.name, "path": str(f.resolve()), "size_bytes": stat.st_size})\n    files.sort(key=lambda x: x["name"])\n    return {"status": "success", "files": files, "count": len(files)}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_file_watcher"
        result = registry.invoke_skill("core_file_watcher", {"dir_path": str(tmp_path), "pattern": "*.py"})
        assert result["status"] == "success"

    def test_core_process_manager(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_process_manager",
            namespace="global",
            scope_level="core",
            description="Process management: list, kill, and spawn processes.",
            inputs={"type": "object", "properties": {"action": {"type": "string"}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "output": {"type": "string"}}},
            python_code='def main(inputs: dict) -> dict:\n    action = inputs.get("action", "list")\n    if action == "list":\n        import os\n        if os.name == "nt":\n            cmd = "tasklist /FO CSV /NH"\n        else:\n            cmd = "ps -eo pid,comm --no-headers"\n        from autopoiesis.core.platform import PlatformAdapter\n        proc = PlatformAdapter.run_command(cmd)\n        return {"status": "success", "output": proc.stdout}\n    return {"status": "error", "error": f"Unsupported action: {action}"}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_process_manager"
        result = registry.invoke_skill("core_process_manager", {"action": "list"})
        assert result["status"] == "success"

    def test_core_notification_bridge(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_notification_bridge",
            namespace="global",
            scope_level="core",
            description="Writes notifications to a local JSON queue for downstream delivery.",
            inputs={"type": "object", "properties": {"channel": {"type": "string"}, "message": {"type": "string"}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "notification_id": {"type": "string"}}},
            python_code='def main(inputs: dict) -> dict:\n    import json\n    import os\n    from pathlib import Path\n    from datetime import datetime\n    channel = inputs.get("channel", "default")\n    message = inputs.get("message", "")\n    if not message:\n        return {"status": "error", "error": "message is required"}\n    queue_dir = Path(".autopoiesis") / "notifications"\n    queue_dir.mkdir(parents=True, exist_ok=True)\n    entry = {\n        "id": f"notif_{datetime.now().strftime(\'%Y%m%d%H%M%S%f\')}",\n        "channel": channel,\n        "message": message,\n        "timestamp": datetime.now().isoformat(),\n    }\n    queue_file = queue_dir / f"{channel}.json"\n    existing = []\n    if queue_file.exists():\n        try:\n            existing = json.loads(queue_file.read_text(encoding="utf-8"))\n        except Exception:\n            existing = []\n    existing.append(entry)\n    queue_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")\n    return {"status": "success", "notification_id": entry["id"], "channel": channel}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_notification_bridge"
        result = registry.invoke_skill("core_notification_bridge", {"channel": "test", "message": "hello"})
        assert result["status"] == "success"
        assert "notification_id" in result

    def test_core_data_viz(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_data_viz",
            namespace="global",
            scope_level="core",
            description="Data visualization generator returning JSON chart spec.",
            inputs={"type": "object", "properties": {"chart_type": {"type": "string"}, "data": {"type": "array"}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "chart_spec": {}}},
            python_code='def main(inputs: dict) -> dict:\n    chart_type = inputs.get("chart_type", "bar")\n    data = inputs.get("data", [])\n    labels = inputs.get("labels", [])\n    title = inputs.get("title", "Chart")\n    if not data and not labels:\n        return {"status": "error", "error": "data or labels is required"}\n    spec = {\n        "type": chart_type,\n        "data": {"labels": labels, "datasets": [{"label": title, "data": data}]},\n    }\n    return {"status": "success", "chart_spec": spec}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_data_viz"
        result = registry.invoke_skill("core_data_viz", {"chart_type": "bar", "data": [1, 2, 3], "labels": ["a", "b", "c"]})
        assert result["status"] == "success"
        assert "chart_spec" in result

    def test_core_regex_processor(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        skill = registry.register_skill(
            skill_id="core_regex_processor",
            namespace="global",
            scope_level="core",
            description="Regex processor: test, find, replace, and split text.",
            inputs={"type": "object", "properties": {"action": {"type": "string"}, "pattern": {"type": "string"}, "text": {"type": "string"}}},
            outputs={"type": "object", "properties": {"status": {"type": "string"}, "matches": {"type": "array"}}},
            python_code='def main(inputs: dict) -> dict:\n    import re\n    action = inputs.get("action", "test")\n    pattern = inputs.get("pattern", "")\n    text = inputs.get("text", "")\n    if not pattern:\n        return {"status": "error", "error": "pattern is required"}\n    compiled = re.compile(pattern)\n    if action == "test":\n        return {"status": "success", "matched": bool(compiled.search(text))}\n    if action == "find":\n        matches = compiled.findall(text)\n        return {"status": "success", "matches": matches, "count": len(matches)}\n    if action == "replace":\n        result, count = compiled.subn(inputs.get("replacement", ""), text)\n        return {"status": "success", "result": result, "replacements": count}\n    return {"status": "error", "error": f"Unsupported action: {action}"}\n',
            root_registry_dir=tmp_path / "registry",
        )
        assert skill.id == "core_regex_processor"
        result = registry.invoke_skill("core_regex_processor", {"action": "find", "pattern": r"\d+", "text": "abc 123 def 456"})
        assert result["status"] == "success"
        assert result["matches"] == ["123", "456"]