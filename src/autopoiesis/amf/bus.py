"""AMF Bus Adapter — standardized message envelopes wrapping AgentMessageBus."""

import uuid
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from pydantic import BaseModel

from autopoiesis.core.messaging import AgentMessageBus
from autopoiesis.core.platform import PlatformAdapter
from autopoiesis.amf.schema import AMFMessage


class AMFBusAdapter:
    """Wraps AgentMessageBus with AMF-standardized message envelopes.

    Provides:
    - Point-to-point messaging with capability routing
    - Channel-based broadcast
    - Request/reply pattern with correlation IDs
    """

    def __init__(self, base_dir: str | Path = ".autopoiesis"):
        self.base_dir = PlatformAdapter.sanitize_path(base_dir)
        self._bus = AgentMessageBus(base_dir=base_dir)
        self._callbacks: Dict[str, Callable] = {}

    def send(
        self,
        sender_agent: str,
        target_agent: str,
        capability: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> AMFMessage:
        """Sends a point-to-point message to a specific agent's channel.

        Args:
            sender_agent: ID of sending agent
            target_agent: ID of receiving agent
            capability: Capability name being invoked
            payload: Message payload
            correlation_id: Optional correlation ID for request/reply tracking
            reply_to: Optional message ID to reply to

        Returns:
            AMFMessage envelope
        """
        channel = f"amf.agent.{target_agent}"
        msg_id = self._bus.publish(
            channel=channel,
            sender=sender_agent,
            payload={
                "capability": capability,
                "payload": payload,
                "correlation_id": correlation_id,
                "reply_to": reply_to,
            },
            reply_to=reply_to,
        )

        return AMFMessage(
            message_id=msg_id,
            sender_agent=sender_agent,
            target_agent=target_agent,
            target_channel=channel,
            capability=capability,
            payload=payload,
            correlation_id=correlation_id,
            reply_to=reply_to,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    def broadcast(
        self,
        channel: str,
        sender_agent: str,
        payload: Dict[str, Any],
        capability: Optional[str] = None,
    ) -> AMFMessage:
        """Broadcasts a message to a channel.

        Args:
            channel: Channel name (e.g. "amf.channel.market_data")
            sender_agent: ID of sending agent
            payload: Message payload
            capability: Optional capability name

        Returns:
            AMFMessage envelope
        """
        msg_id = self._bus.publish(
            channel=channel,
            sender=sender_agent,
            payload={
                "capability": capability,
                "payload": payload,
            },
        )

        return AMFMessage(
            message_id=msg_id,
            sender_agent=sender_agent,
            target_channel=channel,
            capability=capability,
            payload=payload,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    def request_reply(
        self,
        sender_agent: str,
        target_agent: str,
        capability: str,
        payload: Dict[str, Any],
        timeout_sec: float = 30.0,
    ) -> Optional[AMFMessage]:
        """Sends a message and waits for a reply (synchronous-style).
        
        Fixes GAP-I2: Actually polls for the reply message with timeout.
        
        Creates a temporary reply channel and waits for a response.

        Args:
            sender_agent: ID of sending agent
            target_agent: ID of receiving agent
            capability: Capability name
            payload: Request payload
            timeout_sec: Timeout for waiting for reply

        Returns:
            AMFMessage envelope (reply message if received), None if timeout
        """
        import time
        correlation_id = f"corr_{uuid.uuid4().hex[:10]}"
        reply_channel = f"amf.reply.{sender_agent}.{correlation_id}"

        # Subscribe to reply channel and store subscription ID for cleanup
        sub_id = self._bus.subscribe(channel=reply_channel, agent_id=sender_agent)

        try:
            # Send request with reply_to
            request_msg = self.send(
                sender_agent=sender_agent,
                target_agent=target_agent,
                capability=capability,
                payload=payload,
                correlation_id=correlation_id,
                reply_to=reply_channel,
            )

            # Poll for reply (fixes GAP-I2)
            start_time = time.time()
            poll_interval = 0.1  # 100ms poll interval
            while time.time() - start_time < timeout_sec:
                messages = self._bus.get_messages(channel=reply_channel, limit=1, unread_only=True)
                if messages:
                    reply_data = messages[0]
                    # Mark as read
                    self._bus.mark_read(reply_data.get("message_id", ""))
                    return AMFMessage(
                        message_id=reply_data.get("message_id", ""),
                        sender_agent=reply_data.get("sender", target_agent),
                        target_agent=sender_agent,
                        target_channel=reply_channel,
                        capability=reply_data.get("payload", {}).get("capability"),
                        payload=reply_data.get("payload", {}).get("payload", {}),
                        correlation_id=reply_data.get("payload", {}).get("correlation_id"),
                        reply_to=reply_data.get("payload", {}).get("reply_to"),
                        timestamp=reply_data.get("timestamp", ""),
                    )
                time.sleep(poll_interval)

            return None
        finally:
            # Always clean up subscription using subscription ID (fixes I2/N-6)
            self._bus.unsubscribe(sub_id)

    def subscribe(self, channel: str, agent_id: str, callback: Optional[Callable] = None) -> str:
        """Subscribes an agent to a channel.

        Args:
            channel: Channel to subscribe to
            agent_id: Agent subscribing
            callback: Optional callback for new messages

        Returns:
            Subscription ID
        """
        sub_id = self._bus.subscribe(channel=channel, agent_id=agent_id, callback=callback)
        if callback:
            self._callbacks[sub_id] = callback
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribes from a channel."""
        if subscription_id in self._callbacks:
            del self._callbacks[subscription_id]
        return self._bus.unsubscribe(subscription_id)

    def get_messages(self, channel: str, limit: int = 50, unread_only: bool = False) -> List[Dict[str, Any]]:
        """Retrieves messages from a channel."""
        return self._bus.get_messages(channel=channel, limit=limit, unread_only=unread_only)

    def mark_read(self, message_id: str) -> bool:
        """Marks a message as read."""
        return self._bus.mark_read(message_id)

    def list_channels(self) -> List[str]:
        """Lists all active channels."""
        return self._bus.list_channels()

    def get_channel_stats(self) -> Dict[str, Any]:
        """Returns statistics for all channels."""
        return self._bus.get_channel_stats()

    def deliver_to_agent(self, agent_id: str, message: AMFMessage) -> None:
        """Delivers a message to an agent's local channel.

        Used by orchestrator to route messages between composed agents.
        """
        channel = f"amf.agent.{agent_id}"
        self._bus.publish(channel=channel, sender=message.sender_agent, payload={
            "capability": message.capability,
            "payload": message.payload,
            "correlation_id": message.correlation_id,
            "reply_to": message.reply_to,
        })
