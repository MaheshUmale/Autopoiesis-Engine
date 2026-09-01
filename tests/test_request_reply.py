"""Tests for request/reply pattern in AMFBusAdapter.

Fixes TG-3: No tests for request/reply pattern.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopoiesis.amf.bus import AMFBusAdapter
from autopoiesis.amf.schema import AMFMessage


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def bus_adapter(tmp_dir):
    return AMFBusAdapter(base_dir=tmp_dir)


class TestRequestReply:
    def test_request_reply_returns_none_on_timeout(self, bus_adapter):
        """If no reply is received within timeout, should return None."""
        result = bus_adapter.request_reply(
            sender_agent="agent_a",
            target_agent="agent_b",
            capability="test_cap",
            payload={"data": "test"},
            timeout_sec=0.5,  # Short timeout for testing
        )

        assert result is None

    def test_request_reply_subscribes_to_reply_channel(self, bus_adapter):
        """Should subscribe to a reply channel."""
        with patch.object(bus_adapter._bus, "subscribe") as mock_subscribe:
            mock_subscribe.return_value = "sub_id_123"

            bus_adapter.request_reply(
                sender_agent="agent_a",
                target_agent="agent_b",
                capability="test_cap",
                payload={},
                timeout_sec=0.3,
            )

            # Should have subscribed to a reply channel
            mock_subscribe.assert_called_once()
            call_args = mock_subscribe.call_args
            assert "amf.reply.agent_a" in call_args[1].get("channel", "") or "amf.reply.agent_a" in call_args[0][0] if call_args[0] else call_args[1].get("channel", "")

    def test_request_reply_unsubscribes_on_timeout(self, bus_adapter):
        """Should unsubscribe from reply channel on timeout (fixes I2)."""
        with patch.object(bus_adapter._bus, "subscribe") as mock_subscribe:
            with patch.object(bus_adapter._bus, "unsubscribe") as mock_unsubscribe:
                mock_subscribe.return_value = "sub_id_123"
                mock_unsubscribe.return_value = True

                result = bus_adapter.request_reply(
                    sender_agent="agent_a",
                    target_agent="agent_b",
                    capability="test_cap",
                    payload={},
                    timeout_sec=0.3,
                )

                assert result is None
                # Should unsubscribe using subscription ID, not channel name
                mock_unsubscribe.assert_called_once_with("sub_id_123")

    def test_request_reply_returns_message_on_success(self, bus_adapter):
        """Should return reply message when received."""
        # Mock the bus to return a reply message
        reply_message = {
            "message_id": "msg_reply_123",
            "sender": "agent_b",
            "payload": {
                "capability": "test_cap",
                "payload": {"result": "success"},
                "correlation_id": "corr_abc",
                "reply_to": "amf.reply.agent_a.corr_abc",
            },
            "timestamp": "2024-01-01T00:00:00",
        }

        with patch.object(bus_adapter._bus, "subscribe") as mock_subscribe:
            with patch.object(bus_adapter._bus, "get_messages") as mock_get_messages:
                with patch.object(bus_adapter._bus, "mark_read"):
                    with patch.object(bus_adapter._bus, "unsubscribe"):
                        mock_subscribe.return_value = "sub_id_123"
                        # First call returns empty (simulating wait), second returns reply
                        mock_get_messages.side_effect = [
                            [reply_message],
                        ]

                        result = bus_adapter.request_reply(
                            sender_agent="agent_a",
                            target_agent="agent_b",
                            capability="test_cap",
                            payload={"request": "data"},
                            timeout_sec=1.0,
                        )

                        assert result is not None
                        assert isinstance(result, AMFMessage)
                        assert result.sender_agent == "agent_b"
                        assert result.payload["result"] == "success"

    def test_request_reply_sends_with_correlation_id(self, bus_adapter):
        """Should send request with correlation ID and reply_to."""
        with patch.object(bus_adapter, "send") as mock_send:
            mock_send.return_value = AMFMessage(
                message_id="msg_123",
                sender_agent="agent_a",
                target_agent="agent_b",
                capability="test_cap",
                payload={},
            )

            with patch.object(bus_adapter._bus, "subscribe"):
                with patch.object(bus_adapter._bus, "get_messages", return_value=[]):
                    with patch.object(bus_adapter._bus, "unsubscribe"):
                        bus_adapter.request_reply(
                            sender_agent="agent_a",
                            target_agent="agent_b",
                            capability="test_cap",
                            payload={"data": "test"},
                            timeout_sec=0.3,
                        )

                        # Verify send was called with correlation_id and reply_to
                        mock_send.assert_called_once()
                        call_kwargs = mock_send.call_args[1]
                        assert call_kwargs.get("correlation_id") is not None
                        assert call_kwargs.get("reply_to") is not None
                        assert "amf.reply.agent_a" in call_kwargs.get("reply_to", "")


class TestAMFBusAdapterSend:
    def test_send_creates_amf_message(self, bus_adapter):
        with patch.object(bus_adapter._bus, "publish") as mock_publish:
            mock_publish.return_value = "msg_id_123"

            result = bus_adapter.send(
                sender_agent="agent_a",
                target_agent="agent_b",
                capability="test_cap",
                payload={"key": "value"},
            )

            assert isinstance(result, AMFMessage)
            assert result.message_id == "msg_id_123"
            assert result.sender_agent == "agent_a"
            assert result.target_agent == "agent_b"
            assert result.payload == {"key": "value"}

    def test_send_with_correlation_id(self, bus_adapter):
        with patch.object(bus_adapter._bus, "publish") as mock_publish:
            mock_publish.return_value = "msg_id_456"

            result = bus_adapter.send(
                sender_agent="agent_a",
                target_agent="agent_b",
                capability="test_cap",
                payload={},
                correlation_id="corr_789",
                reply_to="amf.reply.agent_a.corr_789",
            )

            assert result.correlation_id == "corr_789"
            assert result.reply_to == "amf.reply.agent_a.corr_789"


class TestAMFBusAdapterBroadcast:
    def test_broadcast_creates_amf_message(self, bus_adapter):
        with patch.object(bus_adapter._bus, "publish") as mock_publish:
            mock_publish.return_value = "msg_id_broadcast"

            result = bus_adapter.broadcast(
                channel="test.channel",
                sender_agent="agent_a",
                payload={"data": "broadcast_data"},
            )

            assert isinstance(result, AMFMessage)
            assert result.message_id == "msg_id_broadcast"
            assert result.payload == {"data": "broadcast_data"}


class TestAMFBusAdapterSubscribe:
    def test_subscribe_returns_subscription_id(self, bus_adapter):
        with patch.object(bus_adapter._bus, "subscribe") as mock_subscribe:
            mock_subscribe.return_value = "sub_id_xyz"

            result = bus_adapter.subscribe(
                channel="test.channel",
                agent_id="agent_a",
            )

            assert result == "sub_id_xyz"

    def test_subscribe_with_callback_stores_callback(self, bus_adapter):
        callback = MagicMock()

        with patch.object(bus_adapter._bus, "subscribe") as mock_subscribe:
            mock_subscribe.return_value = "sub_id_callback"

            sub_id = bus_adapter.subscribe(
                channel="test.channel",
                agent_id="agent_a",
                callback=callback,
            )

            assert sub_id == "sub_id_callback"
            assert sub_id in bus_adapter._callbacks
            assert bus_adapter._callbacks[sub_id] == callback


class TestAMFBusAdapterUnsubscribe:
    def test_unsubscribe_removes_callback(self, bus_adapter):
        # First subscribe
        with patch.object(bus_adapter._bus, "subscribe") as mock_subscribe:
            mock_subscribe.return_value = "sub_id_remove"
            sub_id = bus_adapter.subscribe(
                channel="test.channel",
                agent_id="agent_a",
                callback=MagicMock(),
            )

        # Then unsubscribe
        with patch.object(bus_adapter._bus, "unsubscribe") as mock_unsubscribe:
            mock_unsubscribe.return_value = True

            result = bus_adapter.unsubscribe(sub_id)

            assert result is True
            assert sub_id not in bus_adapter._callbacks
