"""
Attack payload library for KITT demo mode.

30+ payloads mapped to OWASP Top 10 for LLM Applications v2025.2.
Target categories (5/10 — detectable at the gateway layer):
  LLM01: Prompt Injection
  LLM02: Insecure Output Handling
  LLM06: Excessive Agency
  LLM07: System Prompt Leakage
  LLM09: Misinformation

Each payload is tagged with: category, technique, expected detection layer,
OWASP reference, and severity.
"""

import json
import os
from typing import Optional


_PAYLOADS_FILE = os.path.join(os.path.dirname(__file__), "..", "hub", "demo_payloads.json")
_cached: Optional[list[dict]] = None


def load_payloads(category: Optional[str] = None) -> list[dict]:
    """Load attack payloads from JSON file, optionally filtered by category."""
    global _cached
    if _cached is None:
        path = os.path.abspath(_PAYLOADS_FILE)
        if not os.path.exists(path):
            return []
        try:
            with open(path) as f:
                _cached = json.load(f)
        except (json.JSONDecodeError, OSError):
            _cached = []
    payloads = _cached
    if category:
        payloads = [p for p in payloads if p.get("category") == category]
    return payloads


def get_categories() -> list[str]:
    """Return sorted list of unique payload categories."""
    payloads = load_payloads()
    return sorted(set(p.get("category", "unknown") for p in payloads))


def get_payload_count() -> int:
    """Return total number of payloads."""
    return len(load_payloads())


def reload():
    """Force reload payloads from disk (for testing)."""
    global _cached
    _cached = None
