"""Tests for AMF (Agentic Micro-Framework) components."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from autopoiesis.amf.schema import (
    AgentDef,
    Capability,
    Dependency,
    LifecycleHooks,
    AMFManifest,
    WorkflowDef,
    WorkflowNode,
    WorkflowEdge,
    AMFMessage,
    RetryPolicy,
)
from autopoiesis.amf.registry import AMFRegistry
from autopoiesis.amf.lifecycle import AgentLifecycle
from autopoiesis.amf.runtime import AMFRuntime, InvocationResult
from autopoiesis.amf.bus import AMFBusAdapter
from autopoiesis.amf.metrics import AMFMetricsAdapter
from autopoiesis.amf.healing import AMFHealingAdapter
from autopoiesis.amf.orchestrator import AMFOrchestrator


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------

class TestAMFSchema:
    def test_capability_defaults(self):
        cap = Capability(name="test_cap", skill_id="core_data_utilities")
        assert cap.timeout_sec == 30.0
        assert cap.retry_policy.max_attempts == 3
        assert cap.inputs == {}

    def test_dependency_defaults(self):
        dep = Dependency(type="env", name="API_KEY")
        assert dep.required is True
        assert dep.version_constraint == "*"

    def test_lifecycle_hooks_defaults(self):
        hooks = LifecycleHooks()
        assert hooks.on_start == []
        assert hooks.on_stop == []
        assert hooks.on_error == "heal_and_retry"

    def test_agent_def_creation(self):
        agent = AgentDef(
            agent_id="test_agent",
            namespace="test_ns",
            version="2.0.0",
            description="Test agent",
            capabilities=[Capability(name="cap1", skill_id="skill1")],
            dependencies=[Dependency(type="env", name="VAR1")],
            metadata={"key": "value"},
        )
        assert agent.agent_id == "test_agent"
        assert agent.namespace == "test_ns"
        assert len(agent.capabilities) == 1
        assert len(agent.dependencies) == 1

    def test_workflow_def_creation(self):
        workflow = WorkflowDef(
            workflow_id="wf1",
            nodes=[
                WorkflowNode(node_id="n1", agent_id="a1", capability="cap1"),
                WorkflowNode(node_id="n2", agent_id="a2", capability="cap2"),
            ],
            edges=[WorkflowEdge(source="n1", target="n2")],
            parameters={"param1": "value1"},
        )
        assert workflow.workflow_id == "wf1"
        assert len(workflow.nodes) == 2
        assert len(workflow.edges) == 1

    def test_amf_message_creation(self):
        msg = AMFMessage(
            message_id="msg_123",
            sender_agent="agent_a",
            target_agent="agent_b",
            capability="fetch_data",
            payload={"key": "value"},
            correlation_id="corr_456",
        )
        assert msg.message_id == "msg_123"
        assert msg.target_agent == "agent_b"
        assert msg.payload == {"key": "value"}

    def test_amf_manifest_creation(self):
        manifest = AMFManifest(
            project="test_project",
            agents=[AgentDef(agent_id="a1")],
            workflows=[WorkflowDef(workflow_id="wf1")],
        )
        assert manifest.manifest_version == "1.0"
        assert manifest.project == "test_project"
        assert len(manifest.agents) == 1
        assert len(manifest.workflows) == 1

    def test_retry_policy_defaults(self):
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.initial_interval_sec == 1.0


# ---------------------------------------------------------------------------
# AMFRegistry Tests
# ---------------------------------------------------------------------------

class TestAMFRegistry:
    def test_register_and_get_agent(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = AMFRegistry(base_dir=base_dir)
        agent = AgentDef(agent_id="agent_1", namespace="test", description="Test agent")
        record = registry.register_agent(agent)
        assert record.agent_id == "agent_1"
        assert record.state == "created"

        retrieved = registry.get_agent("agent_1")
        assert retrieved is not None
        assert retrieved.agent_id == "agent_1"

        agent_def = registry.get_agent_def("agent_1")
        assert agent_def is not None
        assert agent_def.agent_id == "agent_1"

    def test_list_agents(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = AMFRegistry(base_dir=base_dir)
        registry.register_agent(AgentDef(agent_id="a1", namespace="ns1"))
        registry.register_agent(AgentDef(agent_id="a2", namespace="ns1"))
        registry.register_agent(AgentDef(agent_id="a3", namespace="ns2"))

        all_agents = registry.list_agents()
        assert len(all_agents) == 3

        ns1_agents = registry.list_agents(namespace="ns1")
        assert len(ns1_agents) == 2

    def test_find_capable_agents(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = AMFRegistry(base_dir=base_dir)
        registry.register_agent(AgentDef(
            agent_id="agent_1",
            capabilities=[Capability(name="fetch", skill_id="skill_a")],
        ))
        registry.register_agent(AgentDef(
            agent_id="agent_2",
            capabilities=[Capability(name="fetch", skill_id="skill_b")],
        ))

        capable = registry.find_capable_agents("fetch")
        assert set(capable) == {"agent_1", "agent_2"}

        none_capable = registry.find_capable_agents("nonexistent")
        assert none_capable == []

    def test_update_agent_state(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = AMFRegistry(base_dir=base_dir)
        registry.register_agent(AgentDef(agent_id="a1"))
        assert registry.update_agent_state("a1", "running") is True
        record = registry.get_agent("a1")
        assert record.state == "running"

    def test_unregister_agent(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = AMFRegistry(base_dir=base_dir)
        registry.register_agent(AgentDef(agent_id="a1"))
        assert registry.unregister_agent("a1") is True
        assert registry.get_agent("a1") is None

    def test_resolve_dependencies(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = AMFRegistry(base_dir=base_dir)
        agent = AgentDef(
            agent_id="a1",
            dependencies=[
                Dependency(type="env", name="EXISTING_VAR", required=True),
                Dependency(type="env", name="MISSING_VAR", required=True),
                Dependency(type="skill", name="core_data_utilities", required=True),
            ],
        )
        registry.register_agent(agent)
        result = registry.resolve_dependencies("a1")
        assert result["satisfied"] is False
        assert any("MISSING_VAR" in m for m in result["missing"])

    def test_load_from_manifest_json(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = AMFRegistry(base_dir=base_dir)
        manifest_data = {
            "manifest_version": "1.0",
            "project": "test",
            "agents": [{"agent_id": "json_agent", "namespace": "global"}],
        }
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")
        manifest = registry.load_from_manifest(manifest_file)
        assert manifest.project == "test"
        assert len(manifest.agents) == 1

    def test_register_manifest(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        registry = AMFRegistry(base_dir=base_dir)
        manifest_data = {
            "manifest_version": "1.0",
            "project": "test",
            "agents": [
                {"agent_id": "m_a1", "namespace": "ns1"},
                {"agent_id": "m_a2", "namespace": "ns2"},
            ],
        }
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")
        records = registry.register_manifest(manifest_file)
        assert len(records) == 2


# ---------------------------------------------------------------------------
# AgentLifecycle Tests
# ---------------------------------------------------------------------------

class TestAgentLifecycle:
    def test_create_agent(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        lifecycle = AgentLifecycle(base_dir=base_dir)
        state = lifecycle.create_agent("agent_1", namespace="test")
        assert state.state == "created"
        assert state.session_id is not None

    def test_create_duplicate_raises(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        lifecycle = AgentLifecycle(base_dir=base_dir)
        lifecycle.create_agent("agent_1")
        with pytest.raises(ValueError, match="already exists"):
            lifecycle.create_agent("agent_1")

    def test_start_stop_agent(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        lifecycle = AgentLifecycle(base_dir=base_dir)
        lifecycle.create_agent("agent_1")
        state = lifecycle.start_agent("agent_1")
        assert state.state == "running"

        state = lifecycle.stop_agent("agent_1")
        assert state.state == "stopped"

    def test_pause_resume_agent(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        lifecycle = AgentLifecycle(base_dir=base_dir)
        lifecycle.create_agent("agent_1")
        lifecycle.start_agent("agent_1")
        state = lifecycle.pause_agent("agent_1")
        assert state.state == "paused"

        state = lifecycle.resume_agent("agent_1")
        assert state.state == "running"

    def test_destroy_agent(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        lifecycle = AgentLifecycle(base_dir=base_dir)
        lifecycle.create_agent("agent_1")
        assert lifecycle.destroy_agent("agent_1") is True
        assert lifecycle.get_agent_status("agent_1") is None

    def test_invalid_state_transition(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        lifecycle = AgentLifecycle(base_dir=base_dir)
        lifecycle.create_agent("agent_1")
        with pytest.raises(ValueError, match="Invalid state transition"):
            lifecycle.stop_agent("agent_1")  # created -> stopping not allowed

    def test_get_agent_status(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        lifecycle = AgentLifecycle(base_dir=base_dir)
        lifecycle.create_agent("agent_1", namespace="test_ns", metadata={"owner": "tester"})
        status = lifecycle.get_agent_status("agent_1")
        assert status is not None
        assert status["agent_id"] == "agent_1"
        assert status["state"] == "created"
        assert status["namespace"] == "test_ns"
        assert status["metadata"]["owner"] == "tester"

    def test_list_agents(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        lifecycle = AgentLifecycle(base_dir=base_dir)
        lifecycle.create_agent("a1", namespace="ns1")
        lifecycle.create_agent("a2", namespace="ns2")
        agents = lifecycle.list_agents()
        assert len(agents) == 2


# ---------------------------------------------------------------------------
# AMFRuntime Tests
# ---------------------------------------------------------------------------

class TestAMFRuntime:
    def test_invoke_capability_success(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        # Register a simple skill first
        from autopoiesis.registry.manager import RegistryManager
        reg = RegistryManager(base_dir=base_dir)
        reg.register_skill(
            skill_id="test.echo",
            namespace="global",
            scope_level="core",
            description="Echo skill",
            inputs={"type": "object", "properties": {"message": {"type": "string"}}},
            outputs={"type": "object", "properties": {"echo": {"type": "string"}}},
            python_code='def main(inputs: dict) -> dict:\n    msg = inputs.get("message", "")\n    return {"status": "success", "echo": msg}\n',
            root_registry_dir=base_dir / "registry",
        )

        # Register agent with capability
        from autopoiesis.amf.registry import AMFRegistry
        amf_reg = AMFRegistry(base_dir=base_dir)
        amf_reg.register_agent(AgentDef(
            agent_id="echo_agent",
            capabilities=[Capability(name="echo", skill_id="test.echo")],
        ))

        runtime = AMFRuntime(base_dir=base_dir)
        result = runtime.invoke_capability("echo_agent", "echo", {"message": "hello"})
        assert result.success is True
        assert result.output["echo"] == "hello"

    def test_invoke_capability_agent_not_found(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        runtime = AMFRuntime(base_dir=base_dir)
        result = runtime.invoke_capability("nonexistent", "cap")
        assert result.success is False
        assert "not found" in result.stderr

    def test_invoke_capability_capability_not_found(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        from autopoiesis.amf.registry import AMFRegistry
        amf_reg = AMFRegistry(base_dir=base_dir)
        amf_reg.register_agent(AgentDef(agent_id="a1"))

        runtime = AMFRuntime(base_dir=base_dir)
        result = runtime.invoke_capability("a1", "nonexistent_cap")
        assert result.success is False
        assert "Capability" in result.stderr

    def test_invoke_skill_direct(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        from autopoiesis.registry.manager import RegistryManager
        reg = RegistryManager(base_dir=base_dir)
        reg.register_skill(
            skill_id="test.direct",
            namespace="global",
            scope_level="core",
            description="Direct skill",
            inputs={"type": "object"},
            outputs={"type": "object"},
            python_code='def main(inputs: dict) -> dict:\n    return {"status": "success", "value": 42}\n',
            root_registry_dir=base_dir / "registry",
        )

        runtime = AMFRuntime(base_dir=base_dir)
        result = runtime.invoke_skill("test.direct", {}, {"agent_id": "tester"})
        assert result.success is True
        assert result.output["value"] == 42

    def test_health_check(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        from autopoiesis.amf.registry import AMFRegistry
        amf_reg = AMFRegistry(base_dir=base_dir)
        amf_reg.register_agent(AgentDef(agent_id="healthy_agent"))
        runtime = AMFRuntime(base_dir=base_dir)
        health = runtime.health_check("healthy_agent")
        assert health["agent_id"] == "healthy_agent"
        assert health["healthy"] is True


# ---------------------------------------------------------------------------
# AMFBusAdapter Tests
# ---------------------------------------------------------------------------

class TestAMFBusAdapter:
    def test_send_message(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AMFBusAdapter(base_dir=base_dir)
        msg = bus.send(
            sender_agent="agent_a",
            target_agent="agent_b",
            capability="fetch",
            payload={"data": "test"},
        )
        assert msg.message_id is not None
        assert msg.target_agent == "agent_b"
        assert msg.capability == "fetch"

    def test_broadcast_message(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AMFBusAdapter(base_dir=base_dir)
        msg = bus.broadcast(
            channel="amf.channel.test",
            sender_agent="agent_a",
            payload={"broadcast": True},
            capability="notify",
        )
        assert msg.target_channel == "amf.channel.test"
        messages = bus.get_messages("amf.channel.test")
        assert len(messages) == 1

    def test_subscribe_and_unsubscribe(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AMFBusAdapter(base_dir=base_dir)
        sub_id = bus.subscribe(channel="ch1", agent_id="agent_a")
        assert bus.unsubscribe(sub_id) is True

    def test_list_channels(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AMFBusAdapter(base_dir=base_dir)
        bus.broadcast("ch1", "a", {})
        bus.broadcast("ch2", "b", {})
        channels = bus.list_channels()
        assert set(channels) == {"ch1", "ch2"}

    def test_get_channel_stats(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        bus = AMFBusAdapter(base_dir=base_dir)
        bus.broadcast("ch1", "a", {})
        bus.broadcast("ch1", "b", {})
        stats = bus.get_channel_stats()
        assert stats["ch1"]["message_count"] == 2


# ---------------------------------------------------------------------------
# AMFMetricsAdapter Tests
# ---------------------------------------------------------------------------

class TestAMFMetricsAdapter:
    def test_record_capability_invocation(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        metrics = AMFMetricsAdapter(base_dir=base_dir)
        metrics.record_capability_invocation(
            agent_id="agent_1",
            capability="fetch",
            skill_id="test.fetch",
            success=True,
            execution_time_sec=0.5,
        )
        health = metrics.get_agent_health("agent_1")
        assert health.total_executions == 1
        assert health.success_rate == 100.0

    def test_record_skill_invocation(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        metrics = AMFMetricsAdapter(base_dir=base_dir)
        metrics.record_skill_invocation(
            agent_id="agent_1",
            skill_id="test.skill",
            success=False,
            execution_time_sec=1.0,
            error_type="LogicError",
        )
        health = metrics.get_agent_health("agent_1")
        assert health.total_executions == 1
        assert health.error_distribution.get("LogicError") == 1

    def test_get_system_health(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        metrics = AMFMetricsAdapter(base_dir=base_dir)
        metrics.record_capability_invocation("a1", "cap1", "s1", True, 0.1)
        metrics.record_capability_invocation("a2", "cap2", "s2", False, 0.2)
        system = metrics.get_system_health()
        assert system["total_executions"] == 2
        assert system["agent_count"] == 2

    def test_top_slow_skills(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        metrics = AMFMetricsAdapter(base_dir=base_dir)
        metrics.record_capability_invocation("a1", "slow_cap", "s1", True, 5.0)
        metrics.record_capability_invocation("a1", "fast_cap", "s2", True, 0.1)
        slow = metrics.get_top_slow_skills(1)
        assert len(slow) == 1
        assert slow[0]["capability"] == "slow_cap"


# ---------------------------------------------------------------------------
# AMFHealingAdapter Tests
# ---------------------------------------------------------------------------

class TestAMFHealingAdapter:
    def test_heal_capability_failure_no_cache(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        healing = AMFHealingAdapter(base_dir=base_dir)
        suggestion = healing.heal_capability_failure(
            agent_id="agent_1",
            capability="fetch",
            error_type="NetworkError",
            error_msg="Connection refused",
        )
        assert suggestion.source == "generic"
        assert suggestion.success_rate == 0.0

    def test_heal_capability_failure_with_cache(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        healing = AMFHealingAdapter(base_dir=base_dir)
        # Pre-learn a pattern
        healing.learn_from_failure(
            agent_id="agent_1",
            capability="fetch",
            error_type="NetworkError",
            error_msg="Connection refused",
            fix_code_patch="import time\n# retry\n",
            fix_description="Add retry logic",
        )
        suggestion = healing.heal_capability_failure(
            agent_id="agent_1",
            capability="fetch",
            error_type="NetworkError",
            error_msg="Connection refused",
        )
        assert suggestion.source == "cache"
        assert suggestion.success_rate == 0.0  # 0 uses yet

    def test_learn_and_record_outcome(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        healing = AMFHealingAdapter(base_dir=base_dir)
        pattern_id = healing.learn_from_failure(
            agent_id="agent_1",
            capability="parse",
            error_type="LogicError",
            error_msg="NameError: x",
            fix_code_patch="import x\n",
            fix_description="Import x",
        )
        assert pattern_id is not None
        healing.record_healing_outcome(pattern_id, success=True)
        stats = healing.get_stats()
        assert stats["total_patterns"] >= 1

    def test_generic_patch_by_error_type(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        healing = AMFHealingAdapter(base_dir=base_dir)
        suggestion = healing.heal_capability_failure(
            agent_id="a1",
            capability="transform",
            error_type="TimeoutError",
            error_msg="Timed out",
        )
        assert "chunking" in suggestion.fix_description.lower() or "buffer" in suggestion.fix_description.lower()


# ---------------------------------------------------------------------------
# AMFOrchestrator Tests
# ---------------------------------------------------------------------------

class TestAMFOrchestrator:
    def test_run_workflow_success(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"

        # Register skill and agent
        from autopoiesis.registry.manager import RegistryManager
        reg = RegistryManager(base_dir=base_dir)
        reg.register_skill(
            skill_id="test.echo",
            namespace="global",
            scope_level="core",
            description="Echo skill",
            inputs={"type": "object", "properties": {"message": {"type": "string"}}},
            outputs={"type": "object", "properties": {"echo": {"type": "string"}}},
            python_code='def main(inputs: dict) -> dict:\n    msg = inputs.get("message", "")\n    return {"status": "success", "echo": msg}\n',
            root_registry_dir=base_dir / "registry",
        )

        from autopoiesis.amf.registry import AMFRegistry
        amf_reg = AMFRegistry(base_dir=base_dir)
        amf_reg.register_agent(AgentDef(
            agent_id="echo_agent",
            capabilities=[Capability(name="echo", skill_id="test.echo")],
        ))

        orchestrator = AMFOrchestrator(base_dir=base_dir)
        workflow = WorkflowDef(
            workflow_id="wf_echo",
            nodes=[
                WorkflowNode(node_id="n1", agent_id="echo_agent", capability="echo", inputs={"message": "hello"}),
            ],
            edges=[],
        )
        result = orchestrator.run_workflow(workflow_def=workflow)
        assert result.success is True
        assert "n1" in result.node_outputs
        assert result.node_outputs["n1"]["echo"] == "hello"

    def test_run_workflow_with_edges(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"

        from autopoiesis.registry.manager import RegistryManager
        reg = RegistryManager(base_dir=base_dir)
        reg.register_skill(
            skill_id="test.echo",
            namespace="global",
            scope_level="core",
            description="Echo skill",
            inputs={"type": "object", "properties": {"message": {"type": "string"}}},
            outputs={"type": "object", "properties": {"echo": {"type": "string"}}},
            python_code='def main(inputs: dict) -> dict:\n    msg = inputs.get("message", "")\n    return {"status": "success", "echo": msg}\n',
            root_registry_dir=base_dir / "registry",
        )

        from autopoiesis.amf.registry import AMFRegistry
        amf_reg = AMFRegistry(base_dir=base_dir)
        amf_reg.register_agent(AgentDef(
            agent_id="echo_agent",
            capabilities=[Capability(name="echo", skill_id="test.echo")],
        ))

        orchestrator = AMFOrchestrator(base_dir=base_dir)
        workflow = WorkflowDef(
            workflow_id="wf_chain",
            nodes=[
                WorkflowNode(node_id="n1", agent_id="echo_agent", capability="echo", inputs={"message": "step1"}),
                WorkflowNode(node_id="n2", agent_id="echo_agent", capability="echo", inputs={"message": "{{ step_1.output.echo }}"}),
            ],
            edges=[WorkflowEdge(source="n1", target="n2")],
        )
        result = orchestrator.run_workflow(workflow_def=workflow)
        assert result.success is True
        assert result.node_outputs["n2"]["echo"] == "step1"

    def test_workflow_status_tracking(self, tmp_path: Path):
        base_dir = tmp_path / ".autopoiesis"
        orchestrator = AMFOrchestrator(base_dir=base_dir)
        # Status should be None for non-existent workflow
        status = orchestrator.get_workflow_status("nonexistent")
        assert status is None


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestAMFIntegration:
    def test_full_lifecycle(self, tmp_path: Path):
        """Test complete agent lifecycle: create -> start -> invoke -> stop -> destroy."""
        base_dir = tmp_path / ".autopoiesis"

        from autopoiesis.registry.manager import RegistryManager
        reg = RegistryManager(base_dir=base_dir)
        reg.register_skill(
            skill_id="test.echo",
            namespace="global",
            scope_level="core",
            description="Echo skill",
            inputs={"type": "object", "properties": {"message": {"type": "string"}}},
            outputs={"type": "object", "properties": {"echo": {"type": "string"}}},
            python_code='def main(inputs: dict) -> dict:\n    msg = inputs.get("message", "")\n    return {"status": "success", "echo": msg}\n',
            root_registry_dir=base_dir / "registry",
        )

        from autopoiesis.amf.registry import AMFRegistry
        amf_reg = AMFRegistry(base_dir=base_dir)
        amf_reg.register_agent(AgentDef(
            agent_id="test_agent",
            capabilities=[Capability(name="echo", skill_id="test.echo")],
        ))

        lifecycle = AgentLifecycle(base_dir=base_dir)
        runtime = AMFRuntime(base_dir=base_dir)
        metrics = AMFMetricsAdapter(base_dir=base_dir)

        # Create
        state = lifecycle.create_agent("test_agent", metadata={"purpose": "testing"})
        assert state.state == "created"

        # Start
        state = lifecycle.start_agent("test_agent")
        assert state.state == "running"

        # Invoke
        result = runtime.invoke_capability("test_agent", "echo", {"message": "integration_test"})
        assert result.success is True
        assert result.output["echo"] == "integration_test"

        # Record metrics
        metrics.record_capability_invocation(
            agent_id="test_agent",
            capability="echo",
            skill_id="test.echo",
            success=True,
            execution_time_sec=result.execution_time_sec,
        )

        # Check metrics
        health = metrics.get_agent_health("test_agent")
        assert health.total_executions == 1
        assert health.success_rate == 100.0

        # Stop
        state = lifecycle.stop_agent("test_agent")
        assert state.state == "stopped"

        # Destroy
        assert lifecycle.destroy_agent("test_agent") is True

    def test_full_lifecycle_via_mcp_tools(self, tmp_path: Path):
        """End-to-end AMF lifecycle test through MCP server tools: register -> start -> invoke -> status -> stop -> destroy."""
        base_dir = tmp_path / ".autopoiesis"
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "registry").mkdir(parents=True, exist_ok=True)

        from autopoiesis.registry.manager import RegistryManager
        reg = RegistryManager(base_dir=base_dir)
        reg.register_skill(
            skill_id="test.echo",
            namespace="global",
            scope_level="core",
            description="Echo skill",
            inputs={"type": "object", "properties": {"message": {"type": "string"}}},
            outputs={"type": "object", "properties": {"echo": {"type": "string"}}},
            python_code='def main(inputs: dict) -> dict:\n    msg = inputs.get("message", "")\n    return {"status": "success", "echo": msg}\n',
            root_registry_dir=base_dir / "registry",
        )

        from autopoiesis.amf.registry import AMFRegistry
        amf_reg = AMFRegistry(base_dir=base_dir)
        amf_reg.register_agent(AgentDef(
            agent_id="mcp_test_agent",
            capabilities=[Capability(name="echo", skill_id="test.echo")],
        ))

        # Create lifecycle state so the agent appears in list_agents
        from autopoiesis.amf.lifecycle import AgentLifecycle
        lifecycle = AgentLifecycle(base_dir=base_dir)
        lifecycle.create_agent("mcp_test_agent", metadata={"purpose": "testing"})

        from autopoiesis.mcp.server import create_mcp_server
        server = create_mcp_server(base_dir=str(base_dir))

        import asyncio
        import json

        async def call_tool(name, args):
            return await server.call_tool(name, args)

        def parse_tool_result(result):
            if isinstance(result, tuple):
                unstructured = result[0]
                if isinstance(unstructured, list) and unstructured:
                    text = unstructured[0].text if hasattr(unstructured[0], "text") else str(unstructured[0])
                else:
                    text = str(unstructured)
                return json.loads(text)
            elif isinstance(result, list) and result:
                text = result[0].text if hasattr(result[0], "text") else str(result[0])
                return json.loads(text)
            elif isinstance(result, dict):
                return result
            else:
                return json.loads(result)

        # 1. List agents (should show our agent)
        result = asyncio.run(call_tool("amf_list_agents", {}))
        result_data = parse_tool_result(result)
        assert result_data["status"] == "success"
        assert any(a["agent_id"] == "mcp_test_agent" for a in result_data.get("agents", []))

        # 2. Get agent status
        result = asyncio.run(call_tool("amf_get_agent_status", {"agent_id": "mcp_test_agent"}))
        result_data = parse_tool_result(result)
        assert result_data["status"] == "success"
        assert result_data["agent"]["state"] == "created"

        # 3. Start agent
        result = asyncio.run(call_tool("amf_start_agent", {"agent_id": "mcp_test_agent"}))
        result_data = parse_tool_result(result)
        assert result_data["status"] == "success"
        assert result_data["state"] == "running"

        # 4. Invoke capability
        result = asyncio.run(call_tool("amf_invoke_capability", {
            "agent_id": "mcp_test_agent",
            "capability": "echo",
            "inputs": {"message": "hello_mcp"}
        }))
        result_data = parse_tool_result(result)
        assert result_data["status"] == "success"
        assert result_data["output"]["echo"] == "hello_mcp"

        # 5. Get status again
        result = asyncio.run(call_tool("amf_get_agent_status", {"agent_id": "mcp_test_agent"}))
        result_data = parse_tool_result(result)
        assert result_data["status"] == "success"
        assert result_data["agent"]["state"] == "running"

        # 6. Stop agent
        result = asyncio.run(call_tool("amf_stop_agent", {"agent_id": "mcp_test_agent"}))
        result_data = parse_tool_result(result)
        assert result_data["status"] == "success"
        assert result_data["state"] == "stopped"

        # 7. Destroy agent via MCP tool
        result = asyncio.run(call_tool("amf_destroy_agent", {"agent_id": "mcp_test_agent"}))
        result_data = parse_tool_result(result)
        assert result_data["status"] == "success"

    def test_manifest_round_trip(self, tmp_path: Path):
        """Test loading manifest, registering agents, and persisting to disk."""
        base_dir = tmp_path / ".autopoiesis"
        registry = AMFRegistry(base_dir=base_dir)

        manifest = AMFManifest(
            project="round_trip_test",
            agents=[
                AgentDef(
                    agent_id="rt_agent",
                    namespace="test",
                    capabilities=[Capability(name="cap1", skill_id="skill1")],
                )
            ],
        )

        # Save manifest
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest.model_dump()), encoding="utf-8")

        # Register from file
        records = registry.register_manifest(manifest_file)
        assert len(records) == 1
        assert records[0].agent_id == "rt_agent"

        # Verify persistence
        agent_def = registry.get_agent_def("rt_agent")
        assert agent_def is not None
        assert len(agent_def.capabilities) == 1
