"""
Shared health check logic for KITT services.

Used by Hub /health, Agent Zero daemon, and Dashboard posture score.
Single source of truth for service connectivity checks.
"""

import requests


MCP_URL = "http://localhost:8000"
OLLAMA_URL = "http://localhost:11434"


def check_services() -> dict:
    """
    Check connectivity to core KITT services.
    Returns dict: {service_name: "ok" | "degraded" | "down"}
    """
    checks = {}
    try:
        r = requests.get(f"{MCP_URL}/health", timeout=2)
        checks["mcp"] = "ok" if r.status_code == 200 else "degraded"
    except Exception:
        checks["mcp"] = "down"
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        checks["ollama"] = "ok" if r.status_code == 200 else "degraded"
    except Exception:
        checks["ollama"] = "down"
    return checks


def overall_status(checks: dict) -> str:
    """Return 'ok' if all checks pass, else 'degraded'."""
    return "ok" if all(v == "ok" for v in checks.values()) else "degraded"
