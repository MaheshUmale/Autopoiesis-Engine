"""Tests for agentic support system components."""

import pytest
import json
import time
from pathlib import Path

from autopoiesis.core.session import AgentSessionManager
from autopoiesis.core.messaging import AgentMessageBus
from autopoiesis.core.observability import AgenticObservability
from autopoiesis.core.healing import HealLearningCache
from autopoiesis.core.pattern_parser import PatternIntentParser
from autopoiesis.registry.manager import RegistryManager
from autopoiesis.core.intent import LookAheadParser, ProjectConfig


# ---------------------------------------------------------------------------
# Session Manager Tests
# ---------------------------------------------------------------------------

class TestAgentSessionManager:
    def test_create_session(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        mgr = AgentSessionManager(base_dir=base_dir)
        sid = mgr.create_session(agent_id="agent_1", namespace="global")
        assert sid.startswith("sess_")
        session = mgr.get_session(sid)
        assert session is not None
        assert session["metadata"]["agent_id"] == "agent_1"
        assert session["metadata"]["namespace"] == "global"

    def test_memory_operations(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        mgr = AgentSessionManager(base_dir=base_dir)
        sid = mgr.create_session(agent_id="agent_1")
        assert mgr.set_memory(sid, "key1", "value1") is True
        assert mgr.get_memory(sid, "key1") == "value1"
        assert mgr.get_memory(sid, "missing", "default") == "default"
        assert mgr.get_all_memory(sid) == {"key1": "value1"}

    def test_context_operations(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        mgr = AgentSessionManager(base_dir=base_dir)
        sid = mgr.create_session(agent_id="agent_1")
        mgr.set_context(sid, "cwd", "/tmp/work")
        assert mgr.get_context(sid, "cwd") == "/tmp/work"

    def test_history_tracking(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        mgr = AgentSessionManager(base_dir=base_dir)
        sid = mgr.create_session(agent_id="agent_1")
        mgr.append_history(sid, "tool_a", {"in": 1}, {"out": 2}, True)
        mgr.append_history(sid, "tool_b", {"in": 2}, {"err": "x"}, False, error="x")
        history = mgr.get_recent_history(sid, limit=5)
        assert len(history) == 2
        assert history[0]["tool"] == "tool_a"
        assert history[0]["success"] is True
        assert history[1]["success"] is False
        assert history[1]["error"] == "x"

    def test_get_or_create_session(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        mgr = AgentSessionManager(base_dir=base_dir)
        sid1 = mgr.get_or_create_session(agent_id="agent_1", namespace="ns1")
        sid2 = mgr.get_or_create_session(agent_id="agent_1", namespace="ns1")
        assert sid1 == sid2  # Same agent + namespace returns same session

    def test_close_session(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        mgr = AgentSessionManager(base_dir=base_dir)
        sid = mgr.create_session(agent_id="agent_1")
        assert mgr.close_session(sid) is True
        assert mgr.get_session(sid) is None


# ---------------------------------------------------------------------------
# Message Bus Tests
# ---------------------------------------------------------------------------

class TestAgentMessageBus:
    def test_publish_and_get(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=base_dir)
        msg_id = bus.publish(channel="ch1", sender="agent_1", payload={"text": "hello"})
        assert msg_id.startswith("msg_")
        msgs = bus.get_messages("ch1")
        assert len(msgs) == 1
        assert msgs[0]["payload"]["text"] == "hello"

    def test_subscribe_and_unsubscribe(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=base_dir)
        sub_id = bus.subscribe(channel="ch1", agent_id="agent_1")
        assert bus.unsubscribe(sub_id) is True
        assert bus.unsubscribe("nonexistent") is False

    def test_channel_stats(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=base_dir)
        bus.publish(channel="ch1", sender="a1", payload={})
        bus.publish(channel="ch1", sender="a2", payload={})
        bus.publish(channel="ch2", sender="a1", payload={})
        stats = bus.get_channel_stats()
        assert stats["ch1"]["message_count"] == 2
        assert stats["ch2"]["message_count"] == 1

    def test_list_channels(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=base_dir)
        bus.publish("ch_a", "a", {})
        bus.publish("ch_b", "b", {})
        channels = bus.list_channels()
        assert set(channels) == {"ch_a", "ch_b"}

    # Fixes GAP-T2: Test that callbacks are invoked on message publish
    def test_publish_invokes_callbacks(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=base_dir)
        
        # Track callback invocations
        callback_messages = []
        def test_callback(msg_data):
            callback_messages.append(msg_data)
        
        # Subscribe with callback
        sub_id = bus.subscribe(channel="test_ch", agent_id="agent_1", callback=test_callback)
        
        # Publish a message
        bus.publish(channel="test_ch", sender="agent_2", payload={"text": "hello"})
        
        # Verify callback was invoked
        assert len(callback_messages) == 1
        assert callback_messages[0]["payload"]["text"] == "hello"
        assert callback_messages[0]["sender"] == "agent_2"
        
        # Publish another message
        bus.publish(channel="test_ch", sender="agent_3", payload={"text": "world"})
        assert len(callback_messages) == 2

    def test_callback_error_isolation(self, tmp_path: Path):
        """Test that callback errors don't break message publishing."""
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=base_dir)
        
        # Track if good callback was called
        good_callback_called = []
        def bad_callback(msg_data):
            raise ValueError("Callback error!")
        def good_callback(msg_data):
            good_callback_called.append(msg_data)
        
        # Subscribe both callbacks
        bus.subscribe(channel="error_ch", agent_id="agent_1", callback=bad_callback)
        bus.subscribe(channel="error_ch", agent_id="agent_2", callback=good_callback)
        
        # Publish should not raise even though bad_callback fails
        msg_id = bus.publish(channel="error_ch", sender="agent_3", payload={"test": True})
        assert msg_id.startswith("msg_")
        
        # Good callback should still have been called
        assert len(good_callback_called) == 1

    def test_unsubscribe_removes_callback(self, tmp_path: Path):
        """Test that unsubscribing removes the callback."""
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=base_dir)
        
        callback_messages = []
        def test_callback(msg_data):
            callback_messages.append(msg_data)
        
        sub_id = bus.subscribe(channel="unsub_ch", agent_id="agent_1", callback=test_callback)
        
        # Publish and verify callback is called
        bus.publish(channel="unsub_ch", sender="agent_2", payload={"msg": 1})
        assert len(callback_messages) == 1
        
        # Unsubscribe
        assert bus.unsubscribe(sub_id) is True
        
        # Publish again - callback should not be called
        bus.publish(channel="unsub_ch", sender="agent_2", payload={"msg": 2})
        assert len(callback_messages) == 1  # Still 1, not 2


# ---------------------------------------------------------------------------
# Observability Tests
# ---------------------------------------------------------------------------

class TestAgenticObservability:
    def test_record_and_metrics(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        obs = AgenticObservability(base_dir=base_dir)
        obs.record_execution("skill_a", 0.5, True, None, 1024)
        obs.record_execution("skill_a", 1.0, False, "LogicError", 2048)
        obs.record_execution("skill_b", 0.2, True, None, 512)
        assert obs.total_executions == 3
        assert abs(obs.success_rate - 66.67) < 1.0
        assert abs(obs.avg_execution_time - 0.567) < 0.01

    def test_skill_metrics(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        obs = AgenticObservability(base_dir=base_dir)
        obs.record_execution("skill_x", 0.1, True, None)
        obs.record_execution("skill_x", 0.3, True, None)
        obs.record_execution("skill_x", 0.5, False, "TimeoutError")
        metrics = obs.get_skill_metrics("skill_x")
        assert metrics["total_executions"] == 3
        assert abs(metrics["success_rate"] - 66.67) < 1.0

    def test_error_summary(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        # Use a completely isolated sub-dir to avoid picking up any pre-existing trace files
        isolated_dir = base_dir / "isolated"
        isolated_dir.mkdir(parents=True, exist_ok=True)
        obs = AgenticObservability(base_dir=isolated_dir)
        obs.record_execution("s1", 0.1, False, "LogicError")
        obs.record_execution("s2", 0.2, False, "LogicError")
        obs.record_execution("s3", 0.3, False, "NetworkError")
        summary = obs.get_error_summary()
        assert summary["total_errors"] == 3
        assert summary["by_type"]["LogicError"] == 2


# ---------------------------------------------------------------------------
# Heal Learning Cache Tests
# ---------------------------------------------------------------------------

class TestHealLearningCache:
    def test_learn_and_find(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        cache = HealLearningCache(base_dir=base_dir)
        pattern = cache.learn_pattern(
            skill_id="skill_a",
            error_type="LogicError",
            error_msg="NameError: foo is not defined",
            fix_code_patch="import foo\n",
            fix_description="Import missing module",
        )
        assert pattern.pattern_id is not None
        found = cache.find_suggested_fix("skill_a", "LogicError", "NameError: foo is not defined")
        assert found is not None
        assert found.pattern_id == pattern.pattern_id

    def test_no_suggestion_for_new_error(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        cache = HealLearningCache(base_dir=base_dir)
        result = cache.find_suggested_fix("skill_new", "NetworkError", "Connection refused")
        assert result is None

    def test_record_outcome(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        cache = HealLearningCache(base_dir=base_dir)
        pattern = cache.learn_pattern("s1", "LogicError", "msg1", "patch1", "desc1")
        cache.record_outcome(pattern.pattern_id, success=True)
        cache.record_outcome(pattern.pattern_id, success=False)
        found = cache.find_suggested_fix("s1", "LogicError", "msg1")
        assert found is not None
        assert found.success_count == 1
        assert found.failure_count == 1

    def test_get_stats(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        cache = HealLearningCache(base_dir=base_dir)
        cache.learn_pattern("s1", "E1", "m1", "p1", "d1")
        stats = cache.get_stats()
        assert stats["total_patterns"] == 1

    def test_clear_cache(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        cache = HealLearningCache(base_dir=base_dir)
        cache.learn_pattern("s1", "E1", "m1", "p1", "d1")
        cache.clear()
        assert cache.get_stats()["total_patterns"] == 0


# ---------------------------------------------------------------------------
# PatternIntentParser Tests
# ---------------------------------------------------------------------------

class TestPatternIntentParser:
    def test_classify_intent_fetch(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = PatternIntentParser(registry)
        result = parser.classify_intent("Fetch candles from Upstox and save to Postgres")
        assert result.primary_action == "fetch"
        assert result.confidence > 0.5

    def test_classify_intent_calculate(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = PatternIntentParser(registry)
        result = parser.classify_intent("Calculate 20 SMA from price data")
        assert result.primary_action == "calculate"

    def test_parse_intent_steps(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = PatternIntentParser(registry)
        steps = parser.parse_intent_steps("Fetch data, calculate SMA, and save to file")
        assert len(steps) == 3

    def test_resolve_with_vector_fallback(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = PatternIntentParser(registry)
        results = parser.resolve_with_vector_fallback(
            "Parse JSON data and save results",
            active_namespaces=["global"],
        )
        assert isinstance(results, list)
        assert len(results) <= 5


# ---------------------------------------------------------------------------
# Integrated Intent Resolution Tests
# ---------------------------------------------------------------------------

class TestIntegratedIntentResolution:
    def test_look_ahead_with_pattern_fallback(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        config = ProjectConfig(
            project_id="test_integrated",
            active_namespaces=["global"],
            required_pipeline_intent="Fetch data from API, transform it, and save to file",
        )
        results = parser.resolve_pipeline_intent(config, auto_synthesize=True, root_registry_dir=tmp_path / "registry")
        assert len(results) >= 1
        for res in results:
            assert res.match_found is True

    def test_synthesized_skill_is_functional(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = RegistryManager(base_dir=base_dir)
        parser = LookAheadParser(registry)
        config = ProjectConfig(
            project_id="test_synth",
            active_namespaces=["global"],
            required_pipeline_intent="Send notification alert to ops team",
        )
        results = parser.resolve_pipeline_intent(config, auto_synthesize=True, root_registry_dir=tmp_path / "registry")
        assert len(results) == 1
        skill = registry.get_skill(results[0].skill_id)
        assert skill is not None
        assert Path(skill.file_path).exists()


# ---------------------------------------------------------------------------
# New Seed Skills Tests
# ---------------------------------------------------------------------------

class TestNewSeedSkills:
    def test_http_client_skill(self, tmp_path: Path):
        from autopoiesis.sandbox.executor import SandboxExecutor
        code = """
def main(inputs: dict) -> dict:
    import urllib.request
    url = inputs.get("url", "https://httpbin.org/get")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return {"status": "success", "status_code": resp.status}
"""
        res = SandboxExecutor.execute_skill_code(code, {})
        assert res.success is True

    def test_csv_processor_skill(self, tmp_path: Path):
        from autopoiesis.sandbox.executor import SandboxExecutor
        code = """
import csv, os
def main(inputs: dict) -> dict:
    action = inputs.get("action", "read")
    file_path = inputs.get("file_path", "")
    if action == "read":
        rows = []
        with open(file_path, "r") as f:
            rows = list(csv.DictReader(f))
        return {"status": "success", "rows": rows, "count": len(rows)}
    return {"status": "error", "error": "unsupported"}
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a,b\n1,2\n3,4\n")
        res = SandboxExecutor.execute_skill_code(code, {"action": "read", "file_path": str(csv_file)})
        assert res.success is True
        assert res.output_payload["count"] == 2

    def test_json_path_skill(self, tmp_path: Path):
        from autopoiesis.sandbox.executor import SandboxExecutor
        code = """
def main(inputs: dict) -> dict:
    data = {"users": [{"name": "Alice"}, {"name": "Bob"}]}
    query = inputs.get("query", "users.0.name")
    parts = query.split(".")
    current = data
    for part in parts:
        if part.isdigit():
            current = current[int(part)]
        else:
            current = current[part]
    return {"status": "success", "result": current}
"""
        res = SandboxExecutor.execute_skill_code(code, {"query": "users.0.name"})
        assert res.success is True
        assert res.output_payload["result"] == "Alice"

    def test_regex_processor_skill(self, tmp_path: Path):
        from autopoiesis.sandbox.executor import SandboxExecutor
        code = """
import re
def main(inputs: dict) -> dict:
    action = inputs.get("action", "find")
    pattern = inputs.get("pattern", r"\\d+")
    text = inputs.get("text", "abc 123 def 456")
    compiled = re.compile(pattern)
    if action == "find":
        return {"status": "success", "matches": compiled.findall(text)}
    return {"status": "success"}
"""
        res = SandboxExecutor.execute_skill_code(code, {"action": "find", "pattern": r"\d+", "text": "abc 123 def 456"})
        assert res.success is True
        assert res.output_payload["matches"] == ["123", "456"]


# ---------------------------------------------------------------------------
# MCP Server Integration Tests
# ---------------------------------------------------------------------------

class TestMCPAgenticTools:
    def test_agent_session_create(self, tmp_path: Path):
        from autopoiesis.mcp.server import create_fastapi_app
        from fastapi.testclient import TestClient
        app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
        client = TestClient(app)
        res = client.post("/tools/agent_session_create/execute", json={"agent_id": "test_agent", "namespace": "test_ns"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "session_id" in data

    def test_agent_memory_set_get(self, tmp_path: Path):
        from autopoiesis.mcp.server import create_fastapi_app
        from fastapi.testclient import TestClient
        app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
        client = TestClient(app)
        # Create session
        sres = client.post("/tools/agent_session_create/execute", json={"agent_id": "m1"})
        sid = sres.json()["session_id"]
        # Set memory
        set_res = client.post("/tools/agent_memory_set/execute", json={"session_id": sid, "key": "k1", "value": "v1"})
        assert set_res.status_code == 200
        assert set_res.json()["status"] == "success"
        # Get memory
        get_res = client.post("/tools/agent_memory_get/execute", json={"session_id": sid, "key": "k1"})
        assert get_res.status_code == 200
        assert get_res.json()["value"] == "v1"

    def test_message_bus_publish(self, tmp_path: Path):
        from autopoiesis.mcp.server import create_fastapi_app
        from fastapi.testclient import TestClient
        app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
        client = TestClient(app)
        res = client.post("/tools/message_bus_publish/execute", json={
            "channel": "ch_test",
            "sender": "agent_x",
            "payload": {"msg": "hello"}
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "published"

    def test_observability_metrics(self, tmp_path: Path):
        from autopoiesis.mcp.server import create_fastapi_app
        from fastapi.testclient import TestClient
        app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
        client = TestClient(app)
        res = client.post("/tools/observability_metrics/execute", json={})
        assert res.status_code == 200
        data = res.json()
        assert "total_executions" in data
        assert "success_rate_pct" in data

    def test_heal_suggestion(self, tmp_path: Path):
        from autopoiesis.mcp.server import create_fastapi_app
        from fastapi.testclient import TestClient
        app = create_fastapi_app(base_dir=str(tmp_path / ".autopoiesis"))
        client = TestClient(app)
        res = client.post("/tools/heal_suggestion/execute", json={
            "skill_id": "unknown_skill",
            "error_type": "LogicError",
            "error_msg": "NameError: foo"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "no_suggestion"