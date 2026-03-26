"""Tests for events/report.py — PDF security report generation."""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from events.report import is_available, generate_report


def _sample_events():
    return [
        {"ts": "2026-03-26T10:00:00Z", "layer": "intent_gate", "type": "flag",
         "details": {"category": "prompt_injection", "confidence": 0.9, "flagged": True},
         "severity": "warning", "request_id": "demo-001"},
        {"ts": "2026-03-26T10:00:01Z", "layer": "fan_out", "type": "dispatch",
         "details": {"models": ["claude", "openai"], "prompt_length": 42},
         "severity": "info", "request_id": "demo-001"},
        {"ts": "2026-03-26T10:00:05Z", "layer": "audit", "type": "request_complete",
         "details": {"models_responded": 2, "flags": 1, "intent_flagged": True},
         "severity": "info", "request_id": "demo-001"},
    ]


def _sample_posture():
    return {
        "score": 72,
        "rating": "Moderate",
        "breakdown": {
            "layers_active": 24.0,
            "detection_rate": 18.0,
            "accuracy": 20.0,
            "identity": 10.0,
        },
        "active_layers": ["audit", "fan_out", "intent_gate"],
    }


class TestIsAvailable:
    def test_returns_bool(self):
        result = is_available()
        assert isinstance(result, bool)

    @pytest.mark.skipif(not is_available(), reason="fpdf2 not installed")
    def test_available_when_fpdf2_installed(self):
        assert is_available() is True


@pytest.mark.skipif(not is_available(), reason="fpdf2 not installed")
class TestGenerateReport:
    def test_returns_bytes(self):
        pdf = generate_report(_sample_events(), _sample_posture())
        assert isinstance(pdf, bytes)
        assert len(pdf) > 0

    def test_pdf_starts_with_header(self):
        pdf = generate_report(_sample_events(), _sample_posture())
        assert pdf[:5] == b"%PDF-"

    def test_empty_events(self):
        pdf = generate_report([], _sample_posture())
        assert isinstance(pdf, bytes)
        assert pdf[:5] == b"%PDF-"

    def test_custom_title(self):
        pdf = generate_report(_sample_events(), _sample_posture(), title="Custom Report")
        assert isinstance(pdf, bytes)
        assert len(pdf) > 0

    def test_empty_posture_breakdown(self):
        posture = {"score": 0, "rating": "Weak", "breakdown": {}, "active_layers": []}
        pdf = generate_report(_sample_events(), posture)
        assert isinstance(pdf, bytes)

    def test_many_flagged_events(self):
        events = [
            {"ts": f"2026-03-26T10:00:{i:02d}Z", "layer": "intent_gate", "type": "flag",
             "details": {"category": "jailbreak"}, "severity": "warning", "request_id": f"r-{i}"}
            for i in range(50)
        ]
        pdf = generate_report(events, _sample_posture())
        assert isinstance(pdf, bytes)
        assert len(pdf) > 100

    def test_unicode_in_details(self):
        events = [
            {"ts": "2026-03-26T10:00:00Z", "layer": "intent_gate", "type": "flag",
             "details": {"category": "test", "text": "Unicode: \u2603 \u2764 \u00e9\u00e8"},
             "severity": "warning", "request_id": "unicode-test"},
        ]
        pdf = generate_report(events, _sample_posture())
        assert isinstance(pdf, bytes)
