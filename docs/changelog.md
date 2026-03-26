# Changelog

## 2026-03-26 — `33da6be`

- **feat: Live Threat Defense Dashboard — full implementation**
  - Redis Streams event bus (`events/bus.py`) — structured security event pipeline with `kitt:events` stream
  - Regex-based threat detectors (`events/detectors.py`) — PII, exfiltration, indirect injection detection
  - Dashboard aggregation + security posture score 0-100 (`events/dashboard.py`)
  - Attack payload library (`events/payloads.py` + `hub/demo_payloads.json`) — 30+ OWASP LLM Top 10 mapped payloads
  - PDF security report export (`events/report.py`) — board-ready leave-behind artifact
  - Dashboard UI (`hub/static/dashboard.html`) — real-time event feed, attack replay timeline, model comparison view, demo mode
  - Hub API routes — `/api/dashboard`, `/api/posture`, `/api/demo` (SSE), `/api/replay/*`, `/api/report/pdf`, `/api/payloads`, `/ws/events` (WebSocket)
  - Event emission integrated into Agent Zero (intent gate, fan_out, detectors) and MCP Server (SPIRE identity, context store/retrieve)

- **fix: eng review remediations (10 issues)**
  - Redis Set secondary index for O(1) request_id lookups
  - flags_count double-count bug in audit event
  - bus_available check now actually detects Redis downtime
  - WebSocket xread no longer blocks the event loop (run_in_executor)
  - Shared health module (`shared/health.py`) eliminates 3-way DRY violation
  - PDF report score labels use explicit mapping, not substring matching
  - PDF report handles unicode in event details (latin-1 sanitization)
  - Payload JSON load wrapped in try/except
  - Dashboard refresh debounced during demo mode

- **test: comprehensive test suite added**
  - `tests/test_bus.py` — event bus unit + integration tests
  - `tests/test_detectors.py` — all detector patterns + edge cases
  - `tests/test_dashboard.py` — stats computation + posture score
  - `tests/test_payloads.py` — payload library loading + filtering
  - `tests/test_report.py` — PDF generation + unicode handling
  - `tests/test_hub_routes.py` — all 11 Hub routes, auth enforcement, error cases
  - 83 tests passing, 7 skipped (Redis integration)

- **security: bearer token auth + rate limiting** (committed as `5b8c77c`)
  - Hub API key auth on /chat, /dashboard, and all API endpoints
  - WebSocket auth via query param token
  - Rate limiting on /chat (10/min via slowapi)

## 2026-03-19

- `155cc6e` — **security: scrub secrets, usernames, and internal IPs from tracked files**
  - Redacted SPIRE join token (`fc0aa621-…`) with `<SPIRE_JOIN_TOKEN>` placeholder
  - Removed `spire/bootstrap.crt` and `spire/agent/bootstrap.crt` from tracking
  - Added `*.crt` to `.gitignore`
  - Replaced operator username and `/home/doubl/` paths with `<operator>` placeholders across systemd units, docker-compose files, and gateway manifest
  - Replaced internal subnet `192.168.1.0/24` with `<INTERNAL_SUBNET>/24` in firewall baseline and architecture docs
  - Local docker-compose files restored with real paths via `git skip-worktree`

## 2026-03-19
- Removed "Model & Settings Guidance" section from .claude/CLAUDE.md (cross-repo cleanup)

## 2026-03-19
- Removed "Model & Settings Guidance" section from .claude/CLAUDE.md (cross-repo cleanup)
