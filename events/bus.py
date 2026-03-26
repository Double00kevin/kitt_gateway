"""
Redis Streams event bus for KITT security events.

All security layers emit structured events here. The dashboard
and WebSocket endpoint consume them.

  EMIT PATH:    agent.py / server.py  →  bus.emit()  →  Redis XADD kitt:events
  READ PATH:    dashboard / ws        →  bus.read_events() / bus.stream_events()

Stream retention: MAXLEN ~ 10000 (approximate trim).
Fail-safe: emit() never raises — logs warning and continues.
"""

import json
import os
import redis
from datetime import datetime, timezone
from typing import Optional

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
STREAM_KEY = "kitt:events"
MAX_EVENTS = 10000

_redis: Optional[redis.Redis] = None


def _get_redis() -> Optional[redis.Redis]:
    """Lazy Redis connection with reconnect on failure."""
    global _redis
    if _redis is not None:
        try:
            _redis.ping()
            return _redis
        except (redis.ConnectionError, redis.RedisError):
            _redis = None
    try:
        _redis = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT,
            decode_responses=True, socket_connect_timeout=2
        )
        _redis.ping()
        return _redis
    except (redis.ConnectionError, redis.RedisError):
        _redis = None
        return None


def emit(layer: str, event_type: str, details: dict,
         severity: str = "info", request_id: str = "") -> bool:
    """
    Emit a security event to Redis Streams.
    Returns True if event was written, False on failure (silent).
    """
    if not layer or not event_type:
        return False
    r = _get_redis()
    if r is None:
        return False
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "layer": layer,
        "type": event_type,
        "details": json.dumps(details) if isinstance(details, dict) else str(details),
        "severity": severity,
        "request_id": request_id or "",
    }
    try:
        event_id = r.xadd(STREAM_KEY, event, maxlen=MAX_EVENTS, approximate=True)
        # Secondary index: map request_id → event IDs for fast lookup
        if request_id:
            idx_key = f"kitt:req:{request_id}"
            r.sadd(idx_key, event_id)
            r.expire(idx_key, 86400)  # 24h TTL — matches stream retention window
        return True
    except (redis.RedisError, Exception):
        return False


def read_events(count: int = 100, since: str = "0-0") -> list[dict]:
    """
    Read events from the stream. Returns list of dicts.
    Each dict has: id, ts, layer, type, details (parsed), severity, request_id.
    """
    r = _get_redis()
    if r is None:
        return []
    try:
        raw = r.xrange(STREAM_KEY, min=since, count=count)
    except (redis.RedisError, Exception):
        return []
    events = []
    for event_id, fields in raw:
        try:
            details = json.loads(fields.get("details", "{}"))
        except (json.JSONDecodeError, TypeError):
            details = {"raw": fields.get("details", "")}
        events.append({
            "id": event_id,
            "ts": fields.get("ts", ""),
            "layer": fields.get("layer", ""),
            "type": fields.get("type", ""),
            "details": details,
            "severity": fields.get("severity", "info"),
            "request_id": fields.get("request_id", ""),
        })
    return events


def read_events_by_request(request_id: str) -> list[dict]:
    """Read all events for a specific request_id (for replay)."""
    if not request_id:
        return []
    r = _get_redis()
    if r is None:
        return []
    idx_key = f"kitt:req:{request_id}"
    try:
        event_ids = r.smembers(idx_key)
    except (redis.RedisError, Exception):
        event_ids = set()
    if not event_ids:
        # Fallback: full scan for events emitted before the index existed
        all_events = read_events(count=MAX_EVENTS)
        return [e for e in all_events if e.get("request_id") == request_id]
    # Fetch each event by ID
    events = []
    for eid in sorted(event_ids):
        try:
            result = r.xrange(STREAM_KEY, min=eid, max=eid, count=1)
            for event_id, fields in result:
                try:
                    details = json.loads(fields.get("details", "{}"))
                except (json.JSONDecodeError, TypeError):
                    details = {"raw": fields.get("details", "")}
                events.append({
                    "id": event_id,
                    "ts": fields.get("ts", ""),
                    "layer": fields.get("layer", ""),
                    "type": fields.get("type", ""),
                    "details": details,
                    "severity": fields.get("severity", "info"),
                    "request_id": fields.get("request_id", ""),
                })
        except (redis.RedisError, Exception):
            continue
    return events


def get_recent_request_ids(count: int = 50) -> list[dict]:
    """Get recent unique request_ids with summary info for replay selection."""
    r = _get_redis()
    if r is None:
        return []
    # Read last 500 events (enough to find recent request_ids without full scan)
    try:
        raw = r.xrevrange(STREAM_KEY, count=500)
    except (redis.RedisError, Exception):
        return []
    events = []
    for event_id, fields in raw:
        try:
            details = json.loads(fields.get("details", "{}"))
        except (json.JSONDecodeError, TypeError):
            details = {"raw": fields.get("details", "")}
        events.append({
            "id": event_id,
            "ts": fields.get("ts", ""),
            "layer": fields.get("layer", ""),
            "type": fields.get("type", ""),
            "details": details,
            "severity": fields.get("severity", "info"),
            "request_id": fields.get("request_id", ""),
        })
    # Reverse to chronological order for processing
    events.reverse()
    seen = {}
    for e in events:
        rid = e.get("request_id", "")
        if not rid:
            continue
        if rid not in seen:
            seen[rid] = {
                "request_id": rid,
                "ts": e["ts"],
                "layers": set(),
                "flagged": False,
                "severity": "info",
            }
        seen[rid]["layers"].add(e["layer"])
        if e.get("severity") == "warning":
            seen[rid]["severity"] = "warning"
            seen[rid]["flagged"] = True
        if e.get("severity") == "critical":
            seen[rid]["severity"] = "critical"
            seen[rid]["flagged"] = True
    result = []
    for rid, info in seen.items():
        info["layers"] = sorted(info["layers"])
        info["event_count"] = len([ev for ev in events if ev.get("request_id") == rid])
        result.append(info)
    result.sort(key=lambda x: x["ts"], reverse=True)
    return result[:count]


def stream_key() -> str:
    """Return the stream key for direct XREAD BLOCK usage in WebSocket."""
    return STREAM_KEY


def event_count() -> int:
    """Return total events in stream."""
    r = _get_redis()
    if r is None:
        return 0
    try:
        return r.xlen(STREAM_KEY)
    except (redis.RedisError, Exception):
        return 0
