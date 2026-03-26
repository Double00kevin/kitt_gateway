"""Tests for events/bus.py — Redis Streams event bus."""

import pytest
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from events import bus


def redis_available():
    """Check if Redis is reachable for integration tests."""
    r = bus._get_redis()
    return r is not None


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
class TestBusIntegration:
    """Integration tests — require running Redis."""

    def setup_method(self):
        """Clean up test events before each test."""
        r = bus._get_redis()
        if r:
            r.delete("kitt:events:test")

    def test_emit_and_read(self):
        # Use the real stream for integration
        ok = bus.emit("test_layer", "test_event", {"key": "value"}, request_id="test-123")
        assert ok is True

        events = bus.read_events(count=10)
        assert len(events) > 0
        last = events[-1]
        assert last["layer"] == "test_layer"
        assert last["type"] == "test_event"
        assert last["request_id"] == "test-123"
        assert last["details"]["key"] == "value"

    def test_emit_returns_false_on_empty_layer(self):
        assert bus.emit("", "test", {}) is False

    def test_emit_returns_false_on_empty_type(self):
        assert bus.emit("layer", "", {}) is False

    def test_read_events_empty_stream(self):
        # Reading with a future ID should return empty
        events = bus.read_events(count=10, since="99999999999-0")
        assert events == []

    def test_event_count(self):
        count = bus.event_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_read_events_by_request(self):
        rid = "test-req-unique"
        bus.emit("layer_a", "type_a", {"a": 1}, request_id=rid)
        bus.emit("layer_b", "type_b", {"b": 2}, request_id=rid)
        bus.emit("layer_c", "type_c", {"c": 3}, request_id="other-req")

        events = bus.read_events_by_request(rid)
        assert len(events) >= 2
        assert all(e["request_id"] == rid for e in events)

    def test_get_recent_request_ids(self):
        rid = "test-recent-ids"
        bus.emit("intent_gate", "flag", {"flagged": True}, severity="warning", request_id=rid)
        bus.emit("fan_out", "dispatch", {"models": ["claude"]}, request_id=rid)

        recent = bus.get_recent_request_ids(count=10)
        assert len(recent) > 0
        match = [r for r in recent if r["request_id"] == rid]
        assert len(match) == 1
        assert match[0]["flagged"] is True


class TestBusUnit:
    """Unit tests — no Redis required."""

    def test_emit_none_layer(self):
        assert bus.emit(None, "test", {}) is False

    def test_emit_none_type(self):
        assert bus.emit("layer", None, {}) is False

    def test_read_events_by_request_empty(self):
        assert bus.read_events_by_request("") == []

    def test_stream_key(self):
        assert bus.stream_key() == "kitt:events"
