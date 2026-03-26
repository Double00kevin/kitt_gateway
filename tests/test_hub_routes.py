"""Tests for hub/main.py — FastAPI route tests using TestClient."""

import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set a known API key before importing the app
os.environ["KITT_HUB_API_KEY"] = "test-key-123"

from fastapi.testclient import TestClient
from hub.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test-key-123"}
BAD_AUTH = {"Authorization": "Bearer wrong-key"}


# --- Auth Tests ---

class TestAuth:
    def test_dashboard_requires_auth(self):
        r = client.get("/dashboard")
        assert r.status_code == 401

    def test_dashboard_rejects_bad_key(self):
        r = client.get("/dashboard", headers=BAD_AUTH)
        assert r.status_code == 403

    def test_api_dashboard_requires_auth(self):
        r = client.get("/api/dashboard")
        assert r.status_code == 401

    def test_api_posture_requires_auth(self):
        r = client.get("/api/posture")
        assert r.status_code == 401

    def test_api_payloads_requires_auth(self):
        r = client.get("/api/payloads")
        assert r.status_code == 401

    def test_api_replay_requests_requires_auth(self):
        r = client.get("/api/replay/requests")
        assert r.status_code == 401

    def test_api_replay_detail_requires_auth(self):
        r = client.get("/api/replay/test-123")
        assert r.status_code == 401

    def test_api_report_pdf_requires_auth(self):
        r = client.get("/api/report/pdf")
        assert r.status_code == 401

    def test_chat_requires_auth(self):
        r = client.post("/chat", json={"prompt": "test"})
        assert r.status_code == 401


# --- Health (no auth required) ---

class TestHealth:
    @patch("hub.main.check_services")
    @patch("hub.main.overall_status")
    def test_health_ok(self, mock_overall, mock_checks):
        mock_checks.return_value = {"mcp": "ok", "ollama": "ok"}
        mock_overall.return_value = "ok"
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "kitt-hub"
        assert "checks" in data

    @patch("hub.main.check_services")
    @patch("hub.main.overall_status")
    def test_health_degraded(self, mock_overall, mock_checks):
        mock_checks.return_value = {"mcp": "down", "ollama": "ok"}
        mock_overall.return_value = "degraded"
        r = client.get("/health")
        assert r.status_code == 503
        assert r.json()["status"] == "degraded"


# --- Index ---

class TestIndex:
    def test_index_serves_html(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")


# --- Dashboard Page ---

class TestDashboardPage:
    def test_dashboard_serves_html(self):
        r = client.get("/dashboard", headers=AUTH)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")


# --- Dashboard API ---

class TestDashboardApi:
    @patch("hub.main.get_dashboard_data")
    def test_api_dashboard(self, mock_data):
        mock_data.return_value = {
            "events": [], "stats": {"total": 0, "by_layer": {}, "by_severity": {}, "by_type": {}, "flagged": 0},
            "posture_score": {"score": 50, "rating": "Moderate", "breakdown": {}, "active_layers": []},
            "health": {"status": "ok", "checks": {}}, "bus_available": True, "total_events": 0,
        }
        r = client.get("/api/dashboard", headers=AUTH)
        assert r.status_code == 200
        data = r.json()
        assert "posture_score" in data
        assert "events" in data


class TestPostureApi:
    @patch("hub.main.get_posture_score")
    def test_api_posture(self, mock_score):
        mock_score.return_value = {"score": 75, "rating": "Moderate", "breakdown": {}, "active_layers": []}
        r = client.get("/api/posture", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["score"] == 75


# --- Payload Library ---

class TestPayloadsApi:
    def test_api_payloads_returns_list(self):
        r = client.get("/api/payloads", headers=AUTH)
        assert r.status_code == 200
        data = r.json()
        assert "payloads" in data
        assert "categories" in data
        assert "total" in data

    def test_api_payloads_filter_category(self):
        r = client.get("/api/payloads?category=prompt_injection", headers=AUTH)
        assert r.status_code == 200
        data = r.json()
        for p in data["payloads"]:
            assert p["category"] == "prompt_injection"


# --- Replay ---

class TestReplayApi:
    @patch("hub.main.bus")
    def test_replay_requests_returns_list(self, mock_bus):
        mock_bus.get_recent_request_ids.return_value = [
            {"request_id": "test-1", "ts": "2026-03-26T10:00:00Z", "layers": ["intent_gate"],
             "flagged": False, "severity": "info", "event_count": 3}
        ]
        r = client.get("/api/replay/requests", headers=AUTH)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    @patch("hub.main.bus")
    def test_replay_detail_returns_events(self, mock_bus):
        mock_bus.read_events_by_request.return_value = [
            {"id": "1-0", "ts": "2026-03-26T10:00:00Z", "layer": "intent_gate",
             "type": "flag", "details": {}, "severity": "info", "request_id": "test-1"}
        ]
        r = client.get("/api/replay/test-1", headers=AUTH)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 1

    @patch("hub.main.bus")
    def test_replay_detail_404_on_missing(self, mock_bus):
        mock_bus.read_events_by_request.return_value = []
        r = client.get("/api/replay/nonexistent", headers=AUTH)
        assert r.status_code == 404


# --- PDF Report ---

class TestReportApi:
    @patch("hub.main.pdf_available")
    def test_report_503_when_fpdf2_missing(self, mock_avail):
        mock_avail.return_value = False
        r = client.get("/api/report/pdf", headers=AUTH)
        assert r.status_code == 503

    @patch("hub.main.generate_report")
    @patch("hub.main.pdf_available")
    @patch("hub.main.get_posture_score")
    @patch("hub.main.bus")
    def test_report_returns_pdf(self, mock_bus, mock_posture, mock_avail, mock_gen):
        mock_avail.return_value = True
        mock_bus.read_events.return_value = []
        mock_posture.return_value = {"score": 50, "rating": "Moderate", "breakdown": {}}
        mock_gen.return_value = b"%PDF-1.4 fake pdf content"
        r = client.get("/api/report/pdf", headers=AUTH)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert "content-disposition" in r.headers

    @patch("hub.main.generate_report")
    @patch("hub.main.pdf_available")
    @patch("hub.main.get_posture_score")
    @patch("hub.main.bus")
    def test_report_500_on_generation_failure(self, mock_bus, mock_posture, mock_avail, mock_gen):
        mock_avail.return_value = True
        mock_bus.read_events.return_value = []
        mock_posture.return_value = {"score": 50, "rating": "Moderate", "breakdown": {}}
        mock_gen.return_value = None
        r = client.get("/api/report/pdf", headers=AUTH)
        assert r.status_code == 500


# --- Demo Mode ---

class TestDemoApi:
    @patch("hub.main.load_payloads")
    def test_demo_404_no_payloads(self, mock_load):
        mock_load.return_value = []
        r = client.post("/api/demo", json={}, headers=AUTH)
        assert r.status_code == 404

    def test_demo_requires_auth(self):
        r = client.post("/api/demo", json={})
        assert r.status_code == 401
