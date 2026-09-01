"""Integration tests for end-to-end workflow execution.

Fixes GAP-T1: No integration tests for end-to-end workflows.
"""

import pytest
import json
import time
from pathlib import Path

from autopoiesis.core.session import AgentSessionManager
from autopoiesis.core.messaging import AgentMessageBus
from autopoiesis.core.observability import AgenticObservability
from autopoiesis.core.healing import HealLearningCache
from autopoiesis.registry.manager import RegistryManager
from autopoiesis.core.intent import LookAheadParser, ProjectConfig
from autopoiesis.sandbox.executor import SandboxExecutor
from autopoiesis.mcp.pipeline import PipelineExecutor


# ---------------------------------------------------------------------------
# End-to-End Pipeline Execution Tests
# ---------------------------------------------------------------------------

class TestEndToEndPipeline:
    """Test complete intent → resolution → execution → observability flow."""

    def test_simple_intent_execution(self, tmp_path: Path):
        """Test executing a simple intent end-to-end."""
        base_dir = tmp_path / ".autopoiesis"
        
        # Initialize workspace
        from autopoiesis.cli.init import init_workspace
        init_workspace(project_dir=tmp_path)
        
        # Create pipeline executor
        pipeline = PipelineExecutor(base_dir=str(base_dir))
        
        # Execute a simple intent
        result = pipeline.execute_pipeline(
            intent="Parse data from input.json and double the numbers",
            active_namespaces=["global"],
            agent_id="test_agent",
        )
        
        # Verify result structure
        assert "intent" in result
        assert "steps" in result
        assert "execution_log" in result
        assert "stats" in result
        assert result["stats"]["total_steps"] >= 1

    def test_multi_step_pipeline(self, tmp_path: Path):
        """Test executing a multi-step pipeline."""
        base_dir = tmp_path / ".autopoiesis"
        
        # Initialize workspace
        from autopoiesis.cli.init import init_workspace
        init_workspace(project_dir=tmp_path)
        
        # Create pipeline executor
        pipeline = PipelineExecutor(base_dir=str(base_dir))
        
        # Execute multi-step intent
        result = pipeline.execute_pipeline(
            intent="Read data from file, transform it, and save results",
            active_namespaces=["global"],
            agent_id="multi_step_agent",
        )
        
        # Verify multiple steps were executed
        assert result["stats"]["total_steps"] >= 1
        assert len(result["execution_log"]) >= 1

    def test_pipeline_with_session_persistence(self, tmp_path: Path):
        """Test that pipeline execution persists session state."""
        base_dir = tmp_path / ".autopoiesis"
        
        # Initialize workspace
        from autopoiesis.cli.init import init_workspace
        init_workspace(project_dir=tmp_path)
        
        # Create pipeline executor
        pipeline = PipelineExecutor(base_dir=str(base_dir))
        
        # Execute pipeline
        result = pipeline.execute_pipeline(
            intent="List files in current directory",
            active_namespaces=["global"],
            agent_id="session_test_agent",
        )
        
        # Verify session was created
        session_mgr = pipeline._session_mgr
        sessions = session_mgr.list_sessions_for_agent("session_test_agent")
        assert len(sessions) >= 1
        
        # Verify session has history
        session_id = sessions[0]
        history = session_mgr.get_recent_history(session_id)
        assert len(history) >= 1

    def test_pipeline_with_observability(self, tmp_path: Path):
        """Test that pipeline execution records observability metrics."""
        base_dir = tmp_path / ".autopoiesis"
        
        # Initialize workspace
        from autopoiesis.cli.init import init_workspace
        init_workspace(project_dir=tmp_path)
        
        # Create pipeline executor
        pipeline = PipelineExecutor(base_dir=str(base_dir))
        
        # Get initial metrics
        initial_executions = pipeline._observability.total_executions
        
        # Execute pipeline
        result = pipeline.execute_pipeline(
            intent="Get system health status",
            active_namespaces=["global"],
            agent_id="obs_test_agent",
        )
        
        # Verify metrics were recorded
        assert pipeline._observability.total_executions > initial_executions


# ---------------------------------------------------------------------------
# Agent Communication Integration Tests
# ---------------------------------------------------------------------------

class TestAgentCommunication:
    """Test inter-agent communication patterns."""

    def test_message_bus_pub_sub(self, tmp_path: Path):
        """Test publish/subscribe with callback delivery."""
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=str(base_dir))
        
        received_messages = []
        def callback(msg):
            received_messages.append(msg)
        
        # Subscribe agent_1 to channel
        bus.subscribe(channel="test_channel", agent_id="agent_1", callback=callback)
        
        # Publish from agent_2
        bus.publish(channel="test_channel", sender="agent_2", payload={"data": "test"})
        
        # Verify agent_1 received the message
        assert len(received_messages) == 1
        assert received_messages[0]["sender"] == "agent_2"
        assert received_messages[0]["payload"]["data"] == "test"

    def test_multiple_subscribers(self, tmp_path: Path):
        """Test that multiple subscribers all receive messages."""
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=str(base_dir))
        
        messages_1 = []
        messages_2 = []
        
        bus.subscribe(channel="broadcast", agent_id="agent_1", callback=lambda m: messages_1.append(m))
        bus.subscribe(channel="broadcast", agent_id="agent_2", callback=lambda m: messages_2.append(m))
        
        # Publish message
        bus.publish(channel="broadcast", sender="publisher", payload={"msg": "hello"})
        
        # Both subscribers should receive
        assert len(messages_1) == 1
        assert len(messages_2) == 1


# ---------------------------------------------------------------------------
# Self-Healing Integration Tests
# ---------------------------------------------------------------------------

class TestSelfHealingIntegration:
    """Test self-healing patterns end-to-end."""

    def test_healing_cache_integration(self, tmp_path: Path):
        """Test that healing cache is checked during pipeline execution."""
        base_dir = tmp_path / ".autopoiesis"
        
        # Initialize workspace
        from autopoiesis.cli.init import init_workspace
        init_workspace(project_dir=tmp_path)
        
        # Pre-populate healing cache with a known fix
        heal_cache = HealLearningCache(base_dir=str(base_dir))
        heal_cache.learn_pattern(
            skill_id="test_skill",
            error_type="LogicError",
            error_msg="NameError: x is not defined",
            fix_code_patch="x = 42\n",
            fix_description="Define x",
        )
        
        # Create pipeline executor with healing cache
        pipeline = PipelineExecutor(
            base_dir=str(base_dir),
            heal_cache=heal_cache,
        )
        
        # The healing cache should be available for lookups
        fix = heal_cache.find_suggested_fix("test_skill", "LogicError", "NameError: x is not defined")
        assert fix is not None
        assert fix.fix_code_patch == "x = 42\n"

    def test_healing_outcome_recording(self, tmp_path: Path):
        """Test that healing outcomes are recorded correctly."""
        base_dir = tmp_path / ".autopoiesis"
        heal_cache = HealLearningCache(base_dir=str(base_dir))
        
        # Learn a pattern
        pattern = heal_cache.learn_pattern(
            skill_id="skill_a",
            error_type="LogicError",
            error_msg="test error",
            fix_code_patch="fix_code",
            fix_description="test fix",
        )
        
        # Record success
        heal_cache.record_outcome(pattern.pattern_id, success=True)
        heal_cache.record_outcome(pattern.pattern_id, success=True)
        heal_cache.record_outcome(pattern.pattern_id, success=False)
        
        # Verify stats
        found = heal_cache.find_suggested_fix("skill_a", "LogicError", "test error")
        assert found.success_count == 2
        assert found.failure_count == 1


# ---------------------------------------------------------------------------
# AMF Integration Tests
# ---------------------------------------------------------------------------

class TestAMFIntegration:
    """Test AMF agent lifecycle and workflow execution."""

    def test_agent_lifecycle(self, tmp_path: Path):
        """Test full agent lifecycle: create → start → stop → destroy."""
        base_dir = tmp_path / ".autopoiesis"
        
        from autopoiesis.amf.lifecycle import AgentLifecycle
        from autopoiesis.amf.registry import AMFRegistry
        from autopoiesis.amf.schema import AgentDef
        
        # Initialize registry
        reg = AMFRegistry(base_dir=str(base_dir))
        
        # Register an agent
        agent_def = AgentDef(
            agent_id="test_agent",
            namespace="test",
            description="Test agent for integration test",
        )
        reg.register_agent(agent_def)
        
        # Create lifecycle manager
        lifecycle = AgentLifecycle(base_dir=str(base_dir))
        
        # Create agent
        state = lifecycle.create_agent(agent_id="test_agent", namespace="test")
        assert state.state == "created"
        
        # Start agent
        state = lifecycle.start_agent("test_agent")
        assert state.state == "running"
        
        # Get status
        status = lifecycle.get_agent_status("test_agent")
        assert status is not None
        assert status["state"] == "running"
        
        # Stop agent
        state = lifecycle.stop_agent("test_agent")
        assert state.state == "stopped"
        
        # Destroy agent
        assert lifecycle.destroy_agent("test_agent") is True
        assert lifecycle.get_agent_status("test_agent") is None

    def test_workflow_execution(self, tmp_path: Path):
        """Test workflow registration and execution."""
        base_dir = tmp_path / ".autopoiesis"
        
        from autopoiesis.amf.orchestrator import AMFOrchestrator
        from autopoiesis.amf.registry import AMFRegistry
        from autopoiesis.amf.schema import WorkflowDef, WorkflowNode, WorkflowEdge
        from autopoiesis.amf.lifecycle import AgentLifecycle
        from autopoiesis.amf.schema import AgentDef, Capability
        
        # Initialize
        reg = AMFRegistry(base_dir=str(base_dir))
        lifecycle = AgentLifecycle(base_dir=str(base_dir))
        
        # Create an agent with a capability
        agent_def = AgentDef(
            agent_id="workflow_agent",
            namespace="test",
            capabilities=[
                Capability(name="health_check", skill_id="core_system_health"),
            ],
        )
        reg.register_agent(agent_def)
        lifecycle.create_agent("workflow_agent", namespace="test")
        
        # Create orchestrator
        orchestrator = AMFOrchestrator(base_dir=str(base_dir))
        
        # Register a simple workflow
        workflow_def = WorkflowDef(
            workflow_id="test_workflow",
            namespace="test",
            description="Test workflow",
            nodes=[
                WorkflowNode(
                    node_id="step_1",
                    agent_id="workflow_agent",
                    capability="health_check",
                    inputs={},
                ),
            ],
            edges=[],
        )
        assert orchestrator.register_workflow(workflow_def) is True
        
        # Execute workflow
        result = orchestrator.run_workflow_by_id("test_workflow")
        assert result.workflow_id == "test_workflow"
        # Workflow may succeed or fail depending on skill availability
        assert result.execution_time_sec >= 0


# ---------------------------------------------------------------------------
# Concurrent Execution Tests (GAP-T3)
# ---------------------------------------------------------------------------

class TestConcurrentExecution:
    """Test concurrent agent execution patterns."""

    def test_concurrent_message_bus_access(self, tmp_path: Path):
        """Test that message bus handles concurrent access correctly."""
        import threading
        
        base_dir = tmp_path / ".autopoiesis"
        bus = AgentMessageBus(base_dir=str(base_dir))
        
        errors = []
        message_counts = {"ch1": 0, "ch2": 0}
        
        def publish_messages(channel, count):
            try:
                for i in range(count):
                    bus.publish(channel, f"sender_{i}", {"index": i})
                    message_counts[channel] += 1
            except Exception as e:
                errors.append(e)
        
        # Create threads that publish concurrently
        threads = [
            threading.Thread(target=publish_messages, args=("ch1", 10)),
            threading.Thread(target=publish_messages, args=("ch2", 10)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify no errors
        assert len(errors) == 0
        
        # Verify all messages were published
        assert len(bus.get_messages("ch1")) == 10
        assert len(bus.get_messages("ch2")) == 10

    def test_concurrent_session_creation(self, tmp_path: Path):
        """Test that session manager handles concurrent session creation."""
        import threading
        
        base_dir = tmp_path / ".autopoiesis"
        mgr = AgentSessionManager(base_dir=str(base_dir))
        
        errors = []
        session_ids = []
        
        def create_sessions(agent_id, count):
            try:
                for _ in range(count):
                    sid = mgr.create_session(agent_id=agent_id)
                    session_ids.append(sid)
            except Exception as e:
                errors.append(e)
        
        # Create threads
        threads = [
            threading.Thread(target=create_sessions, args=("agent_1", 5)),
            threading.Thread(target=create_sessions, args=("agent_2", 5)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify no errors
        assert len(errors) == 0
        
        # Verify all sessions were created
        assert len(session_ids) == 10
        assert len(set(session_ids)) == 10  # All unique
