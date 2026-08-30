import pytest
from autopoiesis.core.wmux import AgentWindowManager


def test_agent_window_manager_initialization():
    wm = AgentWindowManager(session_name="test_autopoiesis")
    assert wm is not None


def test_agent_window_manager_spawn_worker():
    wm = AgentWindowManager(session_name="test_autopoiesis")
    res = wm.spawn_worker_pane("test_worker", "echo Hello")
    assert res is True
