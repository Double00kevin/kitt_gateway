"""Tests for events/payloads.py — attack payload library."""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from events.payloads import load_payloads, get_categories, get_payload_count, reload


class TestPayloads:
    def setup_method(self):
        reload()  # ensure fresh load

    def test_load_all(self):
        payloads = load_payloads()
        assert len(payloads) >= 30  # at least 30 payloads
        for p in payloads:
            assert "id" in p
            assert "prompt" in p
            assert "category" in p
            assert "owasp" in p

    def test_filter_by_category(self):
        pi_payloads = load_payloads(category="prompt_injection")
        assert len(pi_payloads) > 0
        assert all(p["category"] == "prompt_injection" for p in pi_payloads)

    def test_filter_nonexistent_category(self):
        assert load_payloads(category="nonexistent") == []

    def test_get_categories(self):
        cats = get_categories()
        assert "prompt_injection" in cats
        assert "jailbreak" in cats
        assert "benign" in cats
        assert "pii_exposure" in cats

    def test_get_payload_count(self):
        assert get_payload_count() >= 30

    def test_benign_payloads_exist(self):
        benign = load_payloads(category="benign")
        assert len(benign) >= 3  # at least 3 control prompts

    def test_each_payload_has_technique(self):
        for p in load_payloads():
            assert "technique" in p, f"Payload {p['id']} missing technique"

    def test_each_payload_has_severity(self):
        for p in load_payloads():
            assert p.get("severity") in ("info", "warning", "critical"), \
                f"Payload {p['id']} has invalid severity: {p.get('severity')}"
