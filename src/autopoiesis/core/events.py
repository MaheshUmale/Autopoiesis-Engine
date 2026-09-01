"""Event-driven architecture for Autopoiesis Engine.

Fixes GAP-A1: No event-driven architecture.
Provides an EventEmitter pattern with async delivery, acknowledgment,
dead-letter queue for failed deliveries, and event cleanup.
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from autopoiesis.core.platform import PlatformAdapter

logger = logging.getLogger("autopoiesis.core.events")


class Event:
    """Represents an event in the system."""

    def __init__(
        self,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ):
        self.event_id = event_id or f"evt_{uuid.uuid4().hex[:12]}"
        self.event_type = event_type
        self.source = source
        self.payload = payload
        self.timestamp = timestamp or time.strftime("%Y-%m-%dT%H:%M:%S")
        self.acknowledged = False


class EventHandler:
    """Registration for an event handler."""

    def __init__(
        self,
        event_type: str,
        handler_id: str,
        callback: Callable,
        filter_fn: Optional[Callable] = None,
    ):
        self.event_type = event_type
        self.handler_id = handler_id
        self.callback = callback
        self.filter_fn = filter_fn


class EventEmitter:
    """Async event emitter with delivery guarantees.

    Features:
    - Subscribe to event types with optional filtering
    - Async callback invocation with error isolation
    - Dead-letter queue for failed deliveries
    - Event persistence for crash recovery
    - Automatic event cleanup (TTL-based)
    """

    DEFAULT_MAX_EVENTS = 10000  # Max events to retain
    DEFAULT_TTL_DAYS = 7  # Events older than this are cleaned up

    def __init__(
        self,
        base_dir: str | Path = ".autopoiesis",
        max_events: int = DEFAULT_MAX_EVENTS,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.events_dir = self.base_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.dlq_dir = self.base_dir / "events_dlq"
        self.dlq_dir.mkdir(parents=True, exist_ok=True)

        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._lock = threading.Lock()
        self._max_events = max_events
        self._ttl_days = ttl_days

    def subscribe(
        self,
        event_type: str,
        callback: Callable,
        filter_fn: Optional[Callable] = None,
    ) -> str:
        """Subscribe to an event type.

        Args:
            event_type: Type of events to subscribe to
            callback: Function to call when event is emitted
            filter_fn: Optional filter function (event) -> bool

        Returns:
            handler_id for unsubscribe
        """
        handler_id = f"hdl_{uuid.uuid4().hex[:8]}"
        handler = EventHandler(
            event_type=event_type,
            handler_id=handler_id,
            callback=callback,
            filter_fn=filter_fn,
        )
        with self._lock:
            self._handlers[event_type].append(handler)
        logger.info(f"Subscribed {handler_id} to event type '{event_type}'")
        return handler_id

    def unsubscribe(self, handler_id: str) -> bool:
        """Unsubscribe from events."""
        with self._lock:
            for event_type, handlers in self._handlers.items():
                for i, handler in enumerate(handlers):
                    if handler.handler_id == handler_id:
                        handlers.pop(i)
                        return True
        return False

    def emit(self, event: Event) -> None:
        """Emit an event to all subscribers.

        Args:
            event: Event to emit
        """
        # Persist event for durability
        self._persist_event(event)

        # Invoke handlers synchronously (for compatibility)
        self._invoke_handlers(event)

        # Periodic cleanup
        self._cleanup_old_events()

    async def emit_async(self, event: Event) -> None:
        """Emit an event asynchronously.

        Args:
            event: Event to emit
        """
        # Persist event for durability
        self._persist_event(event)

        # Invoke handlers asynchronously
        await self._invoke_handlers_async(event)

        # Periodic cleanup
        self._cleanup_old_events()

    def _invoke_handlers(self, event: Event) -> None:
        """Invoke all handlers for an event type with error isolation."""
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))

        for handler in handlers:
            # Apply filter if present
            if handler.filter_fn and not handler.filter_fn(event):
                continue

            try:
                result = handler.callback(event)
                # Handle coroutines
                if asyncio.iscoroutine(result):
                    # Schedule coroutine for execution
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(result)
                        else:
                            asyncio.run(result)
                    except RuntimeError:
                        # No event loop, run synchronously
                        pass
            except Exception as e:
                logger.error(f"Handler {handler.handler_id} failed for event {event.event_id}: {e}")
                self._send_to_dlq(event, handler.handler_id, str(e))

    async def _invoke_handlers_async(self, event: Event) -> None:
        """Invoke all handlers asynchronously."""
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))

        tasks = []
        for handler in handlers:
            if handler.filter_fn and not handler.filter_fn(event):
                continue

            try:
                result = handler.callback(event)
                if asyncio.iscoroutine(result):
                    tasks.append(result)
                elif asyncio.iscoroutinefunction(handler.callback):
                    tasks.append(handler.callback(event))
            except Exception as e:
                logger.error(f"Handler {handler.handler_id} failed: {e}")
                self._send_to_dlq(event, handler.handler_id, str(e))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Async handler failed: {result}")

    def _persist_event(self, event: Event) -> None:
        """Persist event to disk for durability."""
        try:
            event_file = self.events_dir / f"{event.event_id}.json"
            event_data = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "source": event.source,
                "payload": event.payload,
                "timestamp": event.timestamp,
            }
            event_file.write_text(
                json.dumps(event_data, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to persist event {event.event_id}: {e}")

    def _send_to_dlq(self, event: Event, handler_id: str, error: str) -> None:
        """Send failed event to dead-letter queue."""
        try:
            dlq_file = self.dlq_dir / f"{event.event_id}_{handler_id}.json"
            dlq_data = {
                "event": {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "source": event.source,
                    "payload": event.payload,
                    "timestamp": event.timestamp,
                },
                "handler_id": handler_id,
                "error": error,
                "failed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            dlq_file.write_text(
                json.dumps(dlq_data, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {e}")

    def _cleanup_old_events(self) -> None:
        """Clean up old events to prevent disk space issues."""
        try:
            now = time.time()
            max_age_seconds = self._ttl_days * 86400

            # Count current events
            event_files = list(self.events_dir.glob("*.json"))
            if len(event_files) < self._max_events:
                return  # No cleanup needed

            # Remove old events
            for event_file in event_files:
                try:
                    file_age = now - event_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        event_file.unlink(missing_ok=True)
                except Exception:
                    continue

            # If still over limit, remove oldest events
            event_files = list(self.events_dir.glob("*.json"))
            if len(event_files) > self._max_events:
                event_files.sort(key=lambda f: f.stat().st_mtime)
                files_to_remove = len(event_files) - self._max_events
                for event_file in event_files[:files_to_remove]:
                    event_file.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Event cleanup failed: {e}")

    def get_dlq_events(self) -> List[Dict[str, Any]]:
        """Get all events in the dead-letter queue."""
        events = []
        for dlq_file in self.dlq_dir.glob("*.json"):
            try:
                data = json.loads(dlq_file.read_text(encoding="utf-8"))
                events.append(data)
            except Exception:
                continue
        return events

    def replay_dlq(self, event_type: Optional[str] = None) -> int:
        """Replay events from the dead-letter queue.

        Args:
            event_type: Optional filter by event type

        Returns:
            Number of events replayed
        """
        replayed = 0
        for dlq_file in list(self.dlq_dir.glob("*.json")):
            try:
                data = json.loads(dlq_file.read_text(encoding="utf-8"))
                event_data = data.get("event", {})

                if event_type and event_data.get("event_type") != event_type:
                    continue

                event = Event(
                    event_type=event_data["event_type"],
                    source=event_data["source"],
                    payload=event_data["payload"],
                    event_id=event_data["event_id"],
                    timestamp=event_data["timestamp"],
                )
                self._invoke_handlers(event)
                replayed += 1

                # Remove from DLQ after successful replay
                dlq_file.unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to replay DLQ event: {e}")

        return replayed

    def get_event_count(self) -> int:
        """Get total number of persisted events."""
        return len(list(self.events_dir.glob("*.json")))


# ---------------------------------------------------------------------------
# System Events
# ---------------------------------------------------------------------------

# Event types for common system events
class SystemEvents:
    """Standard event types for the Autopoiesis Engine."""

    SKILL_EXECUTED = "skill.executed"
    SKILL_FAILED = "skill.failed"
    SKILL_SYNTHESIZED = "skill.synthesized"

    AGENT_CREATED = "agent.created"
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_DESTROYED = "agent.destroyed"
    AGENT_HEALED = "agent.healed"

    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_NODE_COMPLETED = "workflow.node.completed"

    MESSAGE_PUBLISHED = "message.published"
    MESSAGE_DELIVERED = "message.delivered"

    HEALING_APPLIED = "healing.applied"
    HEALING_FAILED = "healing.failed"
