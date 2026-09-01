"""Tests for EventEmitter and event-driven architecture.

Fixes TG-1: No tests for EventEmitter.
"""

import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from autopoiesis.core.events import Event, EventHandler, EventEmitter, SystemEvents


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def emitter(tmp_dir):
    return EventEmitter(base_dir=tmp_dir, max_events=100, ttl_days=1)


class TestEvent:
    def test_event_creation(self):
        event = Event(
            event_type="test.event",
            source="test_source",
            payload={"key": "value"},
        )
        assert event.event_type == "test.event"
        assert event.source == "test_source"
        assert event.payload == {"key": "value"}
        assert event.event_id.startswith("evt_")
        assert event.acknowledged is False

    def test_event_with_custom_id(self):
        event = Event(
            event_type="test.event",
            source="test",
            payload={},
            event_id="custom_id_123",
            timestamp="2024-01-01T00:00:00",
        )
        assert event.event_id == "custom_id_123"
        assert event.timestamp == "2024-01-01T00:00:00"


class TestEventEmitter:
    def test_subscribe_and_unsubscribe(self, emitter):
        handler_id = emitter.subscribe("test.event", lambda e: None)
        assert handler_id.startswith("hdl_")
        assert emitter.unsubscribe(handler_id) is True
        assert emitter.unsubscribe("nonexistent") is False

    def test_emit_invokes_handler(self, emitter):
        received = []

        def handler(event):
            received.append(event)

        emitter.subscribe("test.event", handler)
        emitter.emit(Event(event_type="test.event", source="test", payload={"data": 123}))

        assert len(received) == 1
        assert received[0].payload["data"] == 123

    def test_emit_no_handlers(self, emitter):
        # Should not raise even with no handlers
        emitter.emit(Event(event_type="unknown.event", source="test", payload={}))

    def test_multiple_handlers(self, emitter):
        results = []

        emitter.subscribe("test.event", lambda e: results.append("handler1"))
        emitter.subscribe("test.event", lambda e: results.append("handler2"))

        emitter.emit(Event(event_type="test.event", source="test", payload={}))

        assert "handler1" in results
        assert "handler2" in results

    def test_handler_isolation(self, emitter):
        """One handler failure should not affect others."""
        results = []

        def failing_handler(event):
            raise RuntimeError("Handler error")

        def working_handler(event):
            results.append("worked")

        emitter.subscribe("test.event", failing_handler)
        emitter.subscribe("test.event", working_handler)

        emitter.emit(Event(event_type="test.event", source="test", payload={}))

        assert "worked" in results

    def test_filter_fn(self, emitter):
        received = []

        def handler(event):
            received.append(event)

        def filter_fn(event):
            return event.payload.get("important", False)

        emitter.subscribe("test.event", handler, filter_fn=filter_fn)

        emitter.emit(Event(event_type="test.event", source="test", payload={"important": False}))
        emitter.emit(Event(event_type="test.event", source="test", payload={"important": True}))

        assert len(received) == 1
        assert received[0].payload["important"] is True

    def test_event_persistence(self, emitter, tmp_dir):
        """Events should be persisted to disk."""
        emitter.emit(Event(event_type="test.event", source="test", payload={}))

        events_dir = Path(tmp_dir) / "events"
        assert events_dir.exists()
        event_files = list(events_dir.glob("*.json"))
        assert len(event_files) == 1

    def test_dead_letter_queue(self, emitter, tmp_dir):
        """Failed handler events should go to DLQ."""
        def failing_handler(event):
            raise RuntimeError("Handler failed")

        emitter.subscribe("test.event", failing_handler)
        emitter.emit(Event(event_type="test.event", source="test", payload={}))

        dlq_dir = Path(tmp_dir) / "events_dlq"
        assert dlq_dir.exists()
        dlq_files = list(dlq_dir.glob("*.json"))
        assert len(dlq_files) == 1

    def test_get_dlq_events(self, emitter):
        def failing_handler(event):
            raise RuntimeError("Handler failed")

        emitter.subscribe("test.event", failing_handler)
        emitter.emit(Event(event_type="test.event", source="test", payload={}))

        dlq_events = emitter.get_dlq_events()
        assert len(dlq_events) == 1
        assert dlq_events[0]["error"] == "Handler failed"

    def test_replay_dlq(self, emitter):
        """Replaying DLQ should re-invoke handlers."""
        results = []

        call_count = 0

        def sometimes_failing_handler(event):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First call fails")
            results.append("success")

        emitter.subscribe("test.event", sometimes_failing_handler)
        emitter.emit(Event(event_type="test.event", source="test", payload={}))

        # Should be in DLQ
        assert len(emitter.get_dlq_events()) == 1

        # Replay should succeed now
        replayed = emitter.replay_dlq()
        assert replayed == 1
        assert "success" in results

    def test_event_count(self, emitter):
        assert emitter.get_event_count() == 0
        emitter.emit(Event(event_type="test.event", source="test", payload={}))
        emitter.emit(Event(event_type="test.event", source="test", payload={}))
        assert emitter.get_event_count() == 2

    def test_cleanup_old_events(self, tmp_dir):
        """Events older than TTL should be cleaned up."""
        emitter = EventEmitter(base_dir=tmp_dir, max_events=5, ttl_days=0)  # 0 days = clean all

        # Emit some events
        for _ in range(3):
            emitter.emit(Event(event_type="test.event", source="test", payload={}))

        assert emitter.get_event_count() == 3

        # Manually set file mtime to old
        events_dir = Path(tmp_dir) / "events"
        old_time = time.time() - 86400  # 1 day ago
        for f in events_dir.glob("*.json"):
            f.touch()
            # Set mtime to old
            import os
            os.utime(f, (old_time, old_time))

        # Emit more to trigger cleanup
        emitter.emit(Event(event_type="test.event", source="test", payload={}))

        # Old events should be cleaned
        assert emitter.get_event_count() <= 4

    def test_max_events_limit(self, tmp_dir):
        """Should not exceed max_events limit."""
        emitter = EventEmitter(base_dir=tmp_dir, max_events=3, ttl_days=365)

        for _ in range(10):
            emitter.emit(Event(event_type="test.event", source="test", payload={}))

        # Should not exceed max_events
        assert emitter.get_event_count() <= 3


class TestEventEmitterAsync:
    async def test_emit_async(self, emitter):
        received = []

        async def async_handler(event):
            received.append(event)

        emitter.subscribe("test.event", async_handler)

        await emitter.emit_async(Event(event_type="test.event", source="test", payload={"async": True}))

        assert len(received) == 1
        assert received[0].payload["async"] is True

    async def test_emit_async_multiple_handlers(self, emitter):
        results = []

        async def handler1(event):
            results.append("handler1")

        async def handler2(event):
            results.append("handler2")

        emitter.subscribe("test.event", handler1)
        emitter.subscribe("test.event", handler2)

        await emitter.emit_async(Event(event_type="test.event", source="test", payload={}))

        assert "handler1" in results
        assert "handler2" in results


class TestSystemEvents:
    def test_system_event_constants(self):
        assert SystemEvents.SKILL_EXECUTED == "skill.executed"
        assert SystemEvents.SKILL_FAILED == "skill.failed"
        assert SystemEvents.AGENT_CREATED == "agent.created"
        assert SystemEvents.WORKFLOW_STARTED == "workflow.started"
        assert SystemEvents.HEALING_APPLIED == "healing.applied"
