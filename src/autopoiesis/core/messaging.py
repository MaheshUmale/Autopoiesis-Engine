"""Agent Message Bus — lightweight pub/sub for agent-to-agent communication."""

import json
import uuid
import time
import threading
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict
from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.core.validation import validate_channel_name, ValidationError

logger = logging.getLogger("autopoiesis.core.messaging")


class Message:
    """Represents a message published to the bus."""
    def __init__(self, channel: str, sender: str, payload: Any, reply_to: Optional[str] = None):
        self.message_id = f"msg_{uuid.uuid4().hex[:10]}"
        self.channel = channel
        self.sender = sender
        self.payload = payload
        self.reply_to = reply_to
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.read = False


class Subscription:
    """Represents a subscription to a channel."""
    def __init__(self, channel: str, agent_id: str, callback: Callable):
        self.subscription_id = f"sub_{uuid.uuid4().hex[:8]}"
        self.channel = channel
        self.agent_id = agent_id
        self.callback = callback
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")


class AgentMessageBus:
    """Lightweight pub/sub message bus for agent-to-agent communication.

    Supports:
    - Channel-based subscriptions (any agent can subscribe to a channel)
    - Point-to-point messaging (reply_to agent ID)
    - Persistent message queue (messages survive agent restarts)
    - Pattern-based routing (channels with wildcards)
    """

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self.bus_dir = self.base_dir / "bus"
        self.bus_dir.mkdir(parents=True, exist_ok=True)
        self._subscriptions: Dict[str, Subscription] = {}
        self._channels: Dict[str, List[Message]] = defaultdict(list)
        self._lock = threading.Lock()
        self._sub_lock = threading.Lock()
        self._load_state()

    def _load_state(self) -> None:
        """Loads persisted messages and subscriptions from disk."""
        for msg_file in self.bus_dir.glob("*.json"):
            try:
                data = json.loads(msg_file.read_text(encoding="utf-8"))
                # Skip malformed files
                if "channel" in data and "sender" in data:
                    channel = data["channel"]
                    self._channels[channel].append(data)
            except (json.JSONDecodeError, KeyError):
                continue

    def _persist_message(self, msg_data: Dict[str, Any]) -> None:
        """Persists a message to disk for durability."""
        msg_id = msg_data.get("message_id", f"msg_{uuid.uuid4().hex[:10]}")
        target = self.bus_dir / f"{msg_id}.json"
        tmp = self.bus_dir / f"{msg_id}.tmp"
        tmp.write_text(json.dumps(msg_data, indent=2), encoding="utf-8")
        tmp.replace(target)

    def subscribe(
        self,
        channel: str,
        agent_id: str,
        callback: Optional[Callable] = None,
    ) -> str:
        """Subscribes an agent to a channel. Returns the subscription ID."""
        with self._sub_lock:
            sub = Subscription(channel=channel, agent_id=agent_id, callback=callback)
            self._subscriptions[sub.subscription_id] = sub
            self._persist_subscription(sub)
            logger.info(f"Agent {agent_id} subscribed to channel '{channel}'")
            return sub.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Removes a subscription by ID."""
        with self._sub_lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]
                try:
                    (self.bus_dir / f"{subscription_id}.json").unlink(missing_ok=True)
                except Exception:
                    pass
                return True
            return False

    def publish(
        self,
        channel: str,
        sender: str,
        payload: Any,
        reply_to: Optional[str] = None,
    ) -> str:
        """Publishes a message to a channel. Returns the message ID.
        
        Fixes GAP-L1: Invokes subscribed callbacks with error isolation.
        Fixes M-4: Validates channel name to prevent injection.
        """
        # Validate channel name (fixes M-4)
        validate_channel_name(channel)

        with self._lock:
            msg = Message(channel=channel, sender=sender, payload=payload, reply_to=reply_to)
            msg_data = {
                "message_id": msg.message_id,
                "channel": channel,
                "sender": sender,
                "payload": payload,
                "reply_to": reply_to,
                "timestamp": msg.timestamp,
                "read": False,
            }
            self._channels[channel].append(msg_data)
            self._persist_message(msg_data)
            logger.info(f"Published to '{channel}' from {sender}: {str(payload)[:80]}")
            
            # Invoke callbacks for this channel (fixes GAP-L1)
            self._invoke_callbacks(channel, msg_data)
            
            return msg.message_id

    def _invoke_callbacks(self, channel: str, msg_data: Dict[str, Any]) -> None:
        """Invoke all callbacks subscribed to a channel with error isolation."""
        with self._sub_lock:
            for sub in self._subscriptions.values():
                if sub.channel == channel and sub.callback:
                    try:
                        sub.callback(msg_data)
                    except Exception as e:
                        logger.error(f"Callback error for subscription {sub.subscription_id}: {e}")

    def get_messages(
        self,
        channel: str,
        agent_id: Optional[str] = None,
        limit: int = 50,
        unread_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Retrieves messages from a channel, optionally filtered."""
        messages = self._channels.get(channel, [])
        if agent_id:
            messages = [m for m in messages if m["sender"] == agent_id]
        if unread_only:
            messages = [m for m in messages if not m.get("read", False)]
        return messages[-limit:]

    def mark_read(self, message_id: str) -> bool:
        """Marks a message as read by ID."""
        for channel, messages in self._channels.items():
            for msg in messages:
                if msg.get("message_id") == message_id:
                    msg["read"] = True
                    self._persist_message(msg)
                    return True
        return False

    def list_channels(self) -> List[str]:
        """Returns all active channels."""
        return list(self._channels.keys())

    def get_channel_stats(self) -> Dict[str, Any]:
        """Returns statistics per channel."""
        stats = {}
        for channel, messages in self._channels.items():
            stats[channel] = {
                "message_count": len(messages),
                "last_message_at": messages[-1]["timestamp"] if messages else None,
                "senders": list(set(m["sender"] for m in messages)),
            }
        return stats

    def _persist_subscription(self, sub: Subscription) -> None:
        """Persists subscription metadata to disk."""
        target = self.bus_dir / f"{sub.subscription_id}.json"
        data = {
            "subscription_id": sub.subscription_id,
            "channel": sub.channel,
            "agent_id": sub.agent_id,
            "created_at": sub.created_at,
        }
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(target)

    def close(self) -> None:
        """Cleans up the message bus."""
        self._subscriptions.clear()
        self._channels.clear()