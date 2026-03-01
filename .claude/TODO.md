# KITT Sovereign Gateway — TODO

**Last updated:** 2026-03-01

Issues are grouped by category. Bugs are things currently broken or that will break under predictable conditions. Incomplete components are things that are declared/stubbed but not implemented. Priorities are ordered within each section.

---

## Bugs

### ~~B1 — Hardcoded Docker bridge IPs will break on container restart~~ ✅ FIXED 2026-02-28

`MCP_URL` in `agent.py` changed to `http://localhost:8000` (Agent Zero is a host process; MCP port is host-bound).
`REDIS_HOST` in `mcp/docker-compose.yml` changed to `mpx-shared-context` (Docker DNS container name).
`shared_context/docker-compose.yaml` updated to join `kitt_sovereign_net` so the MCP container can resolve `mpx-shared-context` by name.

---

### ~~B2 — Kill switch does not stop the Hub or Agent Zero~~ ✅ FIXED 2026-02-28

Added `sudo systemctl stop kitt-hub` and `sudo systemctl stop agent-zero` to `governance/kill_switch.sh` before the final log line.

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

### B6 — `shared_context/ledger.json` is permanently stale
**File:** `shared_context/ledger.json`

`ledger.json` shows `"active_agents": []` and `"shared_memory": {}`. Nothing in the codebase writes to this file at runtime. It was created manually and never updated. It does not reflect actual system state.

---

## Incomplete Components

### I1 — SPIRE workload attestation not wired to any workload
**Files:** `mcp/server.py:10`, `spire/agent/agent.conf`

`SPIRE_SOCKET = "/run/spire/sockets/agent.sock"` is defined in `mcp/server.py` with a `# For future use` comment. The socket is correctly bind-mounted into `kitt_sandbox`. The SPIRE Agent's Docker workload attestor is configured. But no code anywhere calls the SPIRE workload API to request an SVID. Zero-trust identity enforcement between services is not active.

**Next step:** Use the `pyspiffe` library in the MCP Server to fetch an X.509-SVID from the socket before accepting requests, or use it to mutually authenticate between Agent Zero and the MCP Server.

---

### I2 — Intent gate declared but does not exist
**File:** `a2a/agent_zero/agent-card.json:12`

`"intent_gate_required": true` is declared in Agent Zero's security policy. There is no intent gate implemented anywhere — no prompt classifier, no allow/deny logic, no pre-call validation before `fan_out()` dispatches to external APIs. Any string sent to `POST /chat` is forwarded verbatim to all selected models.

---

### I3 — PQC standard declared but not implemented
**File:** `a2a/agent_zero/agent-card.json:13`

`"pqc_standard": "ML-KEM-768"` is declared. No post-quantum cryptography is present in any part of the stack. All external API calls use standard TLS. SPIRE uses RSA-2048 for the CA key.

---

### I4 — Edge router capabilities are aspirational, not functional
**File:** `a2a_proxy/html/.well-known/agent-card.json:14-18`

The public agent card advertises `pii_masking`, `intent_classification`, and `local_routing` as capabilities of the KITT edge router. None of these are implemented. Llama 3.2 is available locally and could be used to perform pre-screening before external API dispatch, but no such pipeline exists yet.

---

### I5 — Agent Zero daemon loop is disconnected from model routing
**File:** `a2a/agent_zero/agent.py:209-222`

`run_daemon()` only polls telemetry and logs heartbeats. It does not call `fan_out()`, read from MCP, or take any autonomous action. The daemon is alive but passive. Agent Zero's routing capability is only exercised when the Hub explicitly calls `fan_out()` in response to a user request.

---

### ~~I6 — Hub `/health` endpoint does not validate external connectivity~~ ✅ FIXED 2026-03-01

`GET /health` now checks MCP Server (`:8000`) and Ollama (`:11434`) with a 2-second timeout each. Returns `{"status":"ok"}` with HTTP 200 when all dependencies are up; `{"status":"degraded"}` with HTTP 503 and per-service detail when any dependency is down.

---

### I7 — SPIRE bootstrap not finalized
**File:** `spire/agent/agent.conf:8-9`

`insecure_bootstrap: true` was set for initial setup and the join token (`REDACTED_SPIRE_TOKEN_1`) is plaintext in the config. After initial agent attestation the trust bundle should be pinned, `insecure_bootstrap` disabled, and the token rotated or replaced with a more durable attestation method (e.g., x509pop or TPM).

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

### M4 — `SYSTEM_BREAKDOWN.md` predates the Hub and fan_out()
**File:** `SYSTEM_BREAKDOWN.md`

This file was generated before `hub/`, the external API routing, and the MCP docker-compose were in place. Several sections are now inaccurate: the architecture diagram, port map, script purpose table, and data flow diagrams do not include the Hub or the five external AI providers.

---

## Architecture / Coupling

### A1 — Hub imports Agent Zero via `sys.path` injection
**File:** `hub/main.py:1-3`

```python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../a2a/agent_zero')))
from agent import AgentZero
```

This works but ties the Hub tightly to the Agent Zero filesystem path and venv. If `agent.py` gains a new import not present in `hub/venv/`, the Hub crashes at startup with no clear error. If the directory is moved, the Hub breaks.

**Better long-term approach:** Expose Agent Zero as a local HTTP service (it already has MCP_URL and Ollama wired) and have the Hub call it over HTTP, or package `agent.py` as a proper installable module.

---

### A2 — `a2a/agent_zero/agent-card.json` endpoints are localhost references
**File:** `a2a/agent_zero/agent-card.json:11,13`

The capability endpoints listed in Agent Zero's card (`http://localhost:8000`, `http://localhost:11434`) are localhost addresses that are only valid from the host machine. If another agent on the network tried to discover and call these endpoints via the A2A registry, they would fail.

---

## Next Development Priorities

Ordered by impact-to-effort ratio:

1. **Fix hardcoded Docker IPs (B1)** — high breakage risk, one-line fix per location
2. **Commit `kitt-hub.service` to repo (M1)** — low effort, prevents disaster on rebuild
3. **Add `.env.example` (M2)** — two minutes of work, saves future headaches
4. **Fix kill switch to cover all services (B2)** — two extra lines; governance correctness
5. **Parallelize `fan_out()` (B3)** — significant UX improvement; ~30 lines with `ThreadPoolExecutor`
6. **Pin `hub/requirements.txt` (M3)** — run one command
7. **Fix SPIFFE trust domain alignment (B5)** — correctness before SPIRE is relied upon
8. **Fix `orchestrator/router.py` static state write (B4)** — if the orchestrator is used
9. **Implement intent gate (I2)** — use local Llama 3.2 as a pre-screen before external dispatch
10. **Wire SPIRE workload attestation (I1)** — prerequisite for zero-trust enforcement
