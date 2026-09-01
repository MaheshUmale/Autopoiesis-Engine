"""Tests for LocalWorkflowExecutor.

Fixes TG-2: No tests for LocalWorkflowExecutor.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopoiesis.workflows.local_executor import LocalWorkflowExecutor
from autopoiesis.amf.schema import WorkflowDef, WorkflowNode, WorkflowEdge


@pytest.fixture
def tmp_dir():
    """Create a temporary directory that is properly cleaned up."""
    d = tempfile.mkdtemp()
    yield Path(d)
    # Clean up with error handling for Windows file locking
    try:
        shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def executor(tmp_dir):
    return LocalWorkflowExecutor(base_dir=str(tmp_dir))


@pytest.fixture
def simple_workflow():
    """A simple workflow with two nodes in sequence."""
    return WorkflowDef(
        workflow_id="test_workflow",
        namespace="test",
        description="Test workflow",
        nodes=[
            WorkflowNode(
                node_id="node_1",
                agent_id="agent_1",
                capability="cap_1",
                inputs={"input1": "value1"},
            ),
            WorkflowNode(
                node_id="node_2",
                agent_id="agent_2",
                capability="cap_2",
                inputs={"input2": "{{ step_1.output }}"},
            ),
        ],
        edges=[
            WorkflowEdge(source="node_1", target="node_2"),
        ],
        parameters={"param1": "default_value"},
    )


@pytest.fixture
def parallel_workflow():
    """A workflow with parallel nodes (fan-out)."""
    return WorkflowDef(
        workflow_id="parallel_workflow",
        namespace="test",
        description="Parallel test workflow",
        nodes=[
            WorkflowNode(
                node_id="start",
                agent_id="agent_1",
                capability="cap_start",
                inputs={},
            ),
            WorkflowNode(
                node_id="parallel_1",
                agent_id="agent_2",
                capability="cap_p1",
                inputs={},
            ),
            WorkflowNode(
                node_id="parallel_2",
                agent_id="agent_3",
                capability="cap_p2",
                inputs={},
            ),
            WorkflowNode(
                node_id="end",
                agent_id="agent_4",
                capability="cap_end",
                inputs={},
            ),
        ],
        edges=[
            WorkflowEdge(source="start", target="parallel_1"),
            WorkflowEdge(source="start", target="parallel_2"),
            WorkflowEdge(source="parallel_1", target="end"),
            WorkflowEdge(source="parallel_2", target="end"),
        ],
        parameters={},
    )


def _make_mock_runtime():
    """Create a mock runtime that returns successful results."""
    mock_runtime = MagicMock()
    mock_runtime.invoke_capability.return_value = MagicMock(
        success=True,
        output={"result": "success"},
        error_type=None,
        stderr="",
    )
    return mock_runtime


class TestLocalWorkflowExecutor:
    def test_init_creates_checkpoints_dir(self, tmp_dir):
        executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
        assert (tmp_dir / "workflow_checkpoints").exists()

    def test_execute_simple_workflow(self, tmp_dir, simple_workflow):
        mock_runtime = _make_mock_runtime()
        with patch("autopoiesis.workflows.local_executor.AMFRuntime", return_value=mock_runtime):
            executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
            result = executor.execute_workflow(simple_workflow, parameters={"param1": "test"})

        assert result["success"] is True
        assert result["workflow_id"] == "test_workflow"
        assert "execution_id" in result
        assert len(result["completed_nodes"]) == 2

    def test_execute_workflow_emits_events(self, tmp_dir, simple_workflow):
        mock_runtime = _make_mock_runtime()
        with patch("autopoiesis.workflows.local_executor.AMFRuntime", return_value=mock_runtime):
            executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
            executor.execute_workflow(simple_workflow)

        # Check that events were emitted
        events_dir = tmp_dir / "events"
        assert events_dir.exists()
        event_files = list(events_dir.glob("*.json"))
        assert len(event_files) > 0

    def test_execute_workflow_with_failure(self, tmp_dir, simple_workflow):
        mock_runtime = MagicMock()
        mock_runtime.invoke_capability.return_value = MagicMock(
            success=False,
            output=None,
            error_type="RuntimeError",
            stderr="Something went wrong",
        )
        with patch("autopoiesis.workflows.local_executor.AMFRuntime", return_value=mock_runtime):
            executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
            result = executor.execute_workflow(simple_workflow)

        # Should have errors but not crash
        assert result["success"] is False
        assert len(result["errors"]) > 0 or result["resumable"] is True

    def test_checkpoint_saved_after_node(self, tmp_dir, simple_workflow):
        mock_runtime = _make_mock_runtime()
        with patch("autopoiesis.workflows.local_executor.AMFRuntime", return_value=mock_runtime):
            executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
            result = executor.execute_workflow(simple_workflow)
        execution_id = result["execution_id"]

        # Check checkpoint was saved
        checkpoint_file = tmp_dir / "workflow_checkpoints" / f"{execution_id}.json"
        assert checkpoint_file.exists()

        checkpoint_data = json.loads(checkpoint_file.read_text())
        assert checkpoint_data["workflow_id"] == "test_workflow"
        assert "node_1" in checkpoint_data["completed_nodes"]

    def test_resume_from_checkpoint(self, tmp_dir, simple_workflow):
        mock_runtime = _make_mock_runtime()
        with patch("autopoiesis.workflows.local_executor.AMFRuntime", return_value=mock_runtime):
            # First execution
            executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
            result1 = executor.execute_workflow(simple_workflow)
            execution_id = result1["execution_id"]

            # Create new executor (simulating restart)
            executor2 = LocalWorkflowExecutor(base_dir=str(tmp_dir))

            # Resume
            result2 = executor2.resume_workflow(execution_id, simple_workflow)

        assert result2["workflow_id"] == "test_workflow"

    def test_resume_nonexistent_checkpoint(self, tmp_dir, simple_workflow):
        executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
        with pytest.raises(ValueError, match="No checkpoint found"):
            executor.resume_workflow("nonexistent_id", simple_workflow)

    def test_list_checkpoints(self, tmp_dir):
        executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
        # Create a manual checkpoint
        checkpoint_data = {
            "execution_id": "test_exec_1",
            "workflow_id": "test_wf",
            "completed_nodes": ["node_1"],
            "saved_at": "2024-01-01T00:00:00",
        }
        checkpoint_file = tmp_dir / "workflow_checkpoints" / "test_exec_1.json"
        checkpoint_file.write_text(json.dumps(checkpoint_data))

        checkpoints = executor.list_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0]["execution_id"] == "test_exec_1"

    def test_list_checkpoints_filtered_by_workflow(self, tmp_dir):
        executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
        # Create checkpoints for different workflows
        for wf_id, exec_id in [("wf_a", "exec_a"), ("wf_b", "exec_b")]:
            data = {
                "execution_id": exec_id,
                "workflow_id": wf_id,
                "completed_nodes": [],
                "saved_at": "2024-01-01T00:00:00",
            }
            cp_file = tmp_dir / "workflow_checkpoints" / f"{exec_id}.json"
            cp_file.write_text(json.dumps(data))

        checkpoints = executor.list_checkpoints(workflow_id="wf_a")
        assert len(checkpoints) == 1
        assert checkpoints[0]["workflow_id"] == "wf_a"

    def test_resolve_node_inputs_with_parameters(self, tmp_dir):
        executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
        node = WorkflowNode(
            node_id="n1",
            agent_id="a1",
            capability="c1",
            inputs={"param": "{{ parameters.my_param }}"},
        )
        parameters = {"my_param": "resolved_value"}

        resolved = executor._resolve_node_inputs(node, parameters, {}, {})

        assert resolved["param"] == "resolved_value"

    def test_resolve_node_inputs_with_step_output(self, tmp_dir):
        executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
        node = WorkflowNode(
            node_id="n2",
            agent_id="a2",
            capability="c2",
            inputs={"prev": "{{ step_1.output }}"},
        )
        step_map = {"step_1": "actual_node_1"}
        node_outputs = {"actual_node_1": {"data": "output_value"}}

        resolved = executor._resolve_node_inputs(node, {}, node_outputs, step_map)

        assert resolved["prev"] == {"data": "output_value"}

    def test_resolve_node_inputs_plain_value(self, tmp_dir):
        executor = LocalWorkflowExecutor(base_dir=str(tmp_dir))
        node = WorkflowNode(
            node_id="n1",
            agent_id="a1",
            capability="c1",
            inputs={"literal": "plain_string", "number": 42},
        )

        resolved = executor._resolve_node_inputs(node, {}, {}, {})

        assert resolved["literal"] == "plain_string"
        assert resolved["number"] == 42
