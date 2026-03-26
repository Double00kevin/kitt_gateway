"""
Dashboard data aggregation and security posture score.

Posture Score (0-100):
  40 pts — layers active (intent_gate, fan_out, mcp_context, spire_identity, audit)
  30 pts — detection rate (attacks detected / total flagged-eligible requests)
  20 pts — accuracy (1 - false_positives / total_flags)
  10 pts — identity verified (SPIRE SVID present)

Thresholds: 80-100 = Strong, 50-79 = Moderate, 0-49 = Weak
"""

from events import bus
from shared.health import check_services, overall_status


TOTAL_LAYERS = 5  # intent_gate, fan_out, mcp_context, spire_identity, audit


def get_dashboard_data() -> dict:
    """
    Aggregate event data for the dashboard display.
    Returns: {events, stats, posture_score, health, bus_available}
    """
    events = bus.read_events(count=200)
    bus_available = bus._get_redis() is not None

    if not events:
        return {
            "events": [],
            "stats": _empty_stats(),
            "posture_score": _calculate_posture([], {}),
            "health": _get_health(),
            "bus_available": bus_available,
            "total_events": bus.event_count(),
        }

    stats = _compute_stats(events)
    health = _get_health()
    score = _calculate_posture(events, health)

    return {
        "events": events[-50:],  # last 50 for display
        "stats": stats,
        "posture_score": score,
        "health": health,
        "bus_available": True,
        "total_events": bus.event_count(),
    }


def get_posture_score() -> dict:
    """Return just the posture score with breakdown."""
    events = bus.read_events(count=500)
    health = _get_health()
    score = _calculate_posture(events, health)
    return score


def _compute_stats(events: list[dict]) -> dict:
    """Compute aggregate stats from events."""
    by_layer = {}
    by_severity = {"info": 0, "warning": 0, "critical": 0}
    by_type = {}
    flagged_count = 0

    for e in events:
        layer = e.get("layer", "unknown")
        by_layer[layer] = by_layer.get(layer, 0) + 1
        sev = e.get("severity", "info")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        etype = e.get("type", "unknown")
        by_type[etype] = by_type.get(etype, 0) + 1
        if sev in ("warning", "critical"):
            flagged_count += 1

    return {
        "total": len(events),
        "by_layer": by_layer,
        "by_severity": by_severity,
        "by_type": by_type,
        "flagged": flagged_count,
    }


def _calculate_posture(events: list[dict], health: dict) -> dict:
    """
    Calculate security posture score (0-100).
    """
    # Layer activity (40 pts)
    active_layers = set()
    for e in events[-200:]:
        active_layers.add(e.get("layer", ""))
    active_layers.discard("")
    layer_score = (len(active_layers) / TOTAL_LAYERS) * 40 if TOTAL_LAYERS > 0 else 0

    # Detection rate (30 pts)
    total_requests = len([e for e in events if e.get("type") == "request_complete"])
    flagged = len([e for e in events if e.get("severity") in ("warning", "critical")])
    # For demo: detection rate = flagged / total_requests (higher = better at catching)
    detection_score = (flagged / total_requests * 30) if total_requests > 0 else 0

    # Accuracy (20 pts) — penalize gate_error (fail-open = uncertain)
    gate_errors = len([e for e in events if e.get("type") == "flag"
                       and e.get("details", {}).get("category") == "gate_error"])
    total_flags = len([e for e in events if e.get("type") == "flag"])
    if total_flags > 0:
        accuracy_score = (1 - gate_errors / total_flags) * 20
    else:
        accuracy_score = 20  # No flags = no errors = perfect accuracy

    # Identity (10 pts)
    svid_events = [e for e in events if e.get("layer") == "spire_identity"]
    svid_present = any(
        e.get("details", {}).get("svid_present", False) for e in svid_events
    )
    identity_score = 10 if svid_present else 0

    total = round(layer_score + detection_score + accuracy_score + identity_score)
    total = max(0, min(100, total))

    if total >= 80:
        rating = "Strong"
    elif total >= 50:
        rating = "Moderate"
    else:
        rating = "Weak"

    return {
        "score": total,
        "rating": rating,
        "breakdown": {
            "layers_active": round(layer_score, 1),
            "detection_rate": round(detection_score, 1),
            "accuracy": round(accuracy_score, 1),
            "identity": round(identity_score, 1),
        },
        "active_layers": sorted(active_layers),
    }


def _get_health() -> dict:
    """Check service health directly (no HTTP round-trip to Hub)."""
    checks = check_services()
    return {"status": overall_status(checks), "checks": checks}


def _empty_stats() -> dict:
    return {
        "total": 0,
        "by_layer": {},
        "by_severity": {"info": 0, "warning": 0, "critical": 0},
        "by_type": {},
        "flagged": 0,
    }
