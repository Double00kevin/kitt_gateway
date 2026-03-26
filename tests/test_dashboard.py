"""Tests for events/dashboard.py — aggregation and posture score."""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from events.dashboard import _compute_stats, _calculate_posture, _empty_stats


class TestComputeStats:
    def test_empty_events(self):
        stats = _compute_stats([])
        assert stats["total"] == 0
        assert stats["flagged"] == 0

    def test_counts_by_layer(self):
        events = [
            {"layer": "intent_gate", "severity": "warning", "type": "flag"},
            {"layer": "intent_gate", "severity": "info", "type": "flag"},
            {"layer": "fan_out", "severity": "info", "type": "dispatch"},
        ]
        stats = _compute_stats(events)
        assert stats["total"] == 3
        assert stats["by_layer"]["intent_gate"] == 2
        assert stats["by_layer"]["fan_out"] == 1

    def test_counts_flagged(self):
        events = [
            {"layer": "x", "severity": "warning", "type": "flag"},
            {"layer": "x", "severity": "critical", "type": "flag"},
            {"layer": "x", "severity": "info", "type": "flag"},
        ]
        stats = _compute_stats(events)
        assert stats["flagged"] == 2  # warning + critical


class TestCalculatePosture:
    def test_zero_events(self):
        score = _calculate_posture([], {})
        assert score["score"] == 20  # 0 layers + 0 detection + 20 accuracy (no errors) + 0 identity
        assert score["rating"] == "Weak"

    def test_with_active_layers(self):
        events = [
            {"layer": "intent_gate", "severity": "info", "type": "flag", "details": {}},
            {"layer": "fan_out", "severity": "info", "type": "dispatch", "details": {}},
            {"layer": "audit", "severity": "info", "type": "request_complete", "details": {}},
        ]
        score = _calculate_posture(events, {})
        assert score["breakdown"]["layers_active"] > 0
        assert len(score["active_layers"]) == 3

    def test_with_svid_present(self):
        events = [
            {"layer": "spire_identity", "severity": "info", "type": "svid_status",
             "details": {"svid_present": True}},
        ]
        score = _calculate_posture(events, {})
        assert score["breakdown"]["identity"] == 10

    def test_score_clamped_0_100(self):
        score = _calculate_posture([], {})
        assert 0 <= score["score"] <= 100

    def test_rating_thresholds(self):
        # Strong >= 80
        events_strong = [
            {"layer": "intent_gate", "severity": "warning", "type": "flag", "details": {}},
            {"layer": "fan_out", "severity": "info", "type": "dispatch", "details": {}},
            {"layer": "mcp_context", "severity": "info", "type": "store", "details": {}},
            {"layer": "audit", "severity": "info", "type": "request_complete", "details": {}},
            {"layer": "spire_identity", "severity": "info", "type": "svid_status",
             "details": {"svid_present": True}},
        ]
        score = _calculate_posture(events_strong, {})
        # Should have decent score with 5 layers + identity
        assert score["breakdown"]["layers_active"] == 40.0  # 5/5 * 40
        assert score["breakdown"]["identity"] == 10


class TestEmptyStats:
    def test_structure(self):
        stats = _empty_stats()
        assert stats["total"] == 0
        assert "by_layer" in stats
        assert "by_severity" in stats
