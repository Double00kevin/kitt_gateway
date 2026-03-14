# KITT Sovereign Gateway — TODO

**Last updated:** 2026-03-14

Issues are grouped by category. Bugs are things currently broken or that will break under predictable conditions. Incomplete components are things that are declared/stubbed but not implemented. Priorities are ordered within each section.

---

## Bugs

### ~~B1 — Hardcoded Docker bridge IPs will break on container restart~~ ✅ FIXED 2026-02-28

`MCP_URL` in `agent.py` changed to `http://localhost:8000` (Agent Zero is a host process; MCP port is host-bound).
`REDIS_HOST` in `mcp/docker-compose.yml` changed to `mpx-shared-context` (Docker DNS container name).
`shared_context/docker-compose.yaml` updated to join `kitt_sovereign_net` so the MCP container can resolve `mpx-shared-context` by name.

---

### ~~B2 — Kill switch does not stop the Hub or Agent Zero~~ ✅ FIXED 2026-02-28

Added `sudo systemctl stop kitt-hub` and `sudo systemctl stop kitt-agent` to `governance/kill_switch.sh` before the final log line.

---

### ~~B3 — `fan_out()` is sequential — worst-case latency is ~150 seconds~~ ✅ FIXED 2026-02-28

Replaced sequential for-loop with `ThreadPoolExecutor(max_workers=len(valid_models))`. All model calls are dispatched simultaneously; `as_completed` logs each response as it arrives. `store_context` writes remain sequential after all futures resolve to avoid interleaved Redis writes.

---

### ~~B4 — `orchestrator/router.py` always writes a hardcoded static string to Redis~~ ✅ FIXED 2026-03-01

`new_state` changed from the hardcoded string to `response.content` so the actual LLM output is written to the `mission_status` blackboard key.

---

### ~~B5 — SPIFFE trust domain mismatch across agent cards~~ ✅ FIXED 2026-03-01

`a2a/agent_zero/agent-card.json` updated: `spiffe://kitt.local/agent_zero` → `spiffe://mpx.sovereign/agent_zero`. Both agent cards now declare the `mpx.sovereign` trust domain.

---

### ~~B6 — `shared_context/ledger.json` is permanently stale~~ ✅ FIXED 2026-03-13

File deleted — nothing in the codebase read or wrote to it at runtime.

---

## Incomplete Components

### ~~I1 — SPIRE workload attestation not wired to any workload~~ ✅ FIXED 2026-03-14

`mcp/server.py` now has a FastAPI lifespan that fetches the MCP Server's own X.509-SVID from the SPIRE workload API at startup using `spiffe.workloadapi.WorkloadApiClient(socket_path="unix:///run/spire/sockets/agent.sock")`. Fail-open: any exception logs `[SPIRE] SVID fetch failed (fail-open): <reason>` and MCP continues serving normally. Socket bind-mounted `:ro` into `mpx-mcp-server` via `mcp/docker-compose.yml`. `mcp/requirements.txt` pinned (14 packages) with `spiffe==0.2.5` (HewlettPackard py-spiffe). `PYTHONUNBUFFERED=1` added to container env for visible docker logs output. Workload entry registered 2026-03-14 (entry `073f4fd3`); SPIRE agent updated with `/var/run/docker.sock` mount and `pid: host` to enable Docker workload attestation. MCP now logs `[SPIRE] MCP Server SVID: spiffe://mpx.sovereign/mcp` on startup.

---

### ~~I2 — Intent gate declared but does not exist~~ ✅ FIXED 2026-03-13

`check_intent()` added to `agent.py` — pre-screens every prompt via llama3.2 before `fan_out()` fires. Flag-only (never blocks). Categories: `none`, `prompt_injection`, `jailbreak`, `unsafe`. Flagged events logged to `ats_audit.log` (prompt hash only, not plaintext), MCP `kitt_status` namespace, and systemd journal. `hub/main.py` returns `intent_flagged`, `intent_category`, `intent_score` in every `/chat` response.

---

### I3 — PQC standard declared but not implemented
**File:** `a2a/agent_zero/agent-card.json:13`

`"pqc_standard": "ML-KEM-768"` is declared. No post-quantum cryptography is present in any part of the stack. All external API calls use standard TLS. SPIRE uses RSA-2048 for the CA key.

---

### I4 — Edge router capabilities are aspirational, not functional
**File:** `a2a_proxy/html/.well-known/agent-card.json:14-18`

The public agent card advertises `pii_masking`, `intent_classification`, and `local_routing` as capabilities of the KITT edge router. None of these are implemented. Llama 3.2 is available locally and could be used to perform pre-screening before external API dispatch, but no such pipeline exists yet.

---

### ~~I5 — Agent Zero daemon loop is disconnected from model routing~~ ✅ FIXED 2026-03-01

`run_daemon()` now calls `system_health_check()` on every tick: probes MCP (:8000) and Ollama (:11434), captures uptime and container count, and writes a structured JSON status report to MCP under `agent_id="kitt_status"`. Results are also logged to the systemd journal. Readable via `curl http://localhost:8000/context/retrieve?agent_id=kitt_status`.

---

### ~~I6 — Hub `/health` endpoint does not validate external connectivity~~ ✅ FIXED 2026-03-01

`GET /health` now checks MCP Server (`:8000`) and Ollama (`:11434`) with a 2-second timeout each. Returns `{"status":"ok"}` with HTTP 200 when all dependencies are up; `{"status":"degraded"}` with HTTP 503 and per-service detail when any dependency is down.

---

### ~~I7 — SPIRE bootstrap not finalized~~ ✅ FIXED 2026-03-13

Stale CA certs (expired 2026-03-01) wiped from `spire/data/`. Fresh CA generated on server restart. New join token (`fc0aa621-...`) registered and consumed during re-attestation. `insecure_bootstrap` set to `false`; server trust bundle exported to `spire/agent/bootstrap.crt` (mounted read-only into agent container at `/run/spire/config/bootstrap.crt`) and referenced via `trust_bundle_path`. Agent now verifies server TLS against pinned bundle on every connection. Token in config is single-use (already consumed) — retained as emergency re-attestation credential; generate fresh via `docker exec spire-server /opt/spire/bin/spire-server token generate -spiffeID spiffe://mpx.sovereign/spire-agent -ttl 3600` if data dir is ever wiped.

---

## Missing from Repository

### ~~M1 — `kitt-hub.service` not committed to repo~~ ✅ FIXED 2026-02-28

Copied installed unit to `hub/kitt-hub.service`. Install on a new host with:
```bash
sudo cp hub/kitt-hub.service /etc/systemd/system/ && sudo systemctl daemon-reload
```

---

### ~~M2 — No `.env.example` template~~ ✅ FIXED 2026-02-28

Created `a2a/agent_zero/.env.example` with all five required API key stubs.

---

### ~~M3 — `hub/requirements.txt` is unpinned and has no lockfile~~ ✅ FIXED 2026-02-28

Replaced with full `pip freeze` output from the working `hub/venv/` (18 packages pinned).

---

### ~~M4 — `SYSTEM_BREAKDOWN.md` predates the Hub and fan_out()~~ ✅ FIXED 2026-03-01

Full rewrite: architecture diagram, directory structure, file purpose tables, env vars table, all five data flow diagrams, port map, and Docker service registry updated to reflect Hub, fan_out(), MCP docker-compose, external API routing, kitt-agent rename, and current running state.

---

## Architecture / Coupling

### ~~A1 — Hub imports Agent Zero via `sys.path` injection~~ ✅ FIXED 2026-03-13

Agent Zero now runs as a standalone FastAPI HTTP service on loopback `:9001` (`python agent.py serve`), managed by `kitt-agent-http.service`. Hub calls `POST http://127.0.0.1:9001/fan_out` via `requests`; the `sys.path.insert` hack is gone. A `USE_DIRECT_AGENT_ZERO=true` env toggle re-enables the old direct-import path if needed. Hub returns HTTP 503 `{"error":"Agent Zero unavailable"}` if the service is down.

---

### A2 — `a2a/agent_zero/agent-card.json` endpoints are localhost references
**File:** `a2a/agent_zero/agent-card.json:11,13`

The capability endpoints listed in Agent Zero's card (`http://localhost:8000`, `http://localhost:11434`) are localhost addresses that are only valid from the host machine. If another agent on the network tried to discover and call these endpoints via the A2A registry, they would fail.

---

## Known History Contamination

### H1 — `cookies.txt` (Google session cookies) in git history
**Commit:** `2cec9ea` (2026-03-07)

`cookies.txt` was accidentally committed and pushed to both `origin` (GitHub) and `ssd-vault`. It has since been removed from the index and added to `.gitignore` (commits `0bfbd75`, `3dd692a`), but the file remains in the raw git history on both remotes. The cookies are almost certainly expired. A full purge would require `git filter-repo` + force-push to both remotes — deferred as low practical risk.

---

## Next Development Priorities

Ordered by impact-to-effort ratio:

1. ~~**Wire SPIRE attestation (I1)**~~ ✅ DONE — SVID fetch at MCP startup, fail-open
2. ~~**Finalize SPIRE bootstrap (I7)**~~ ✅ DONE
3. ~~**Pin `mcp/requirements.txt`**~~ ✅ DONE — 14 packages pinned with spiffe==0.2.5
4. ~~**Decouple Hub from Agent Zero (A1)**~~ ✅ DONE
5. ~~**Register MCP workload entry in SPIRE**~~ ✅ DONE — entry `073f4fd3`, selectors on compose labels, SPIRE agent now has docker.sock + pid:host
6. **Fix A2A agent-card endpoints (A2)** — replace `localhost` refs with LAN-accessible addresses
7. **Implement edge capabilities (I4)** — `pii_masking`, `intent_classification`, `local_routing`
