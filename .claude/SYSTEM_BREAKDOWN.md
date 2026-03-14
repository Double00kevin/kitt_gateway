# KITT Sovereign Gateway — System Breakdown

**Updated:** 2026-03-14
**Architecture Codename:** MadProjx-v1
**Gateway ID:** KITT-Sovereign-Gateway v1.1.0

---

## 1. High-Level Architecture Overview

KITT Gateway is a **local-first, sovereign AI infrastructure** that fans out prompts to multiple AI backends simultaneously. Local inference runs via Ollama (llama3.2 on NVIDIA GPU); external inference routes to Anthropic Claude, OpenAI GPT-4o, Google Gemini, xAI Grok, and Perplexity. The design follows a "blackboard" pattern — all components share state through Redis — and cryptographic identity is enforced via SPIFFE/SPIRE.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          HOST MACHINE (Linux)                           │
│                                                                         │
│  [systemd: kitt-hub.service :8080]   [systemd: kitt-agent.service]      │
│        │                           [systemd: kitt-agent-http.service]   │
│        │  Browser / LAN client               │  60s health tick         │
│        ▼                                     ▼                          │
│  ┌──────────────┐  POST /fan_out  ┌──────────────────┐                  │
│  │   KITT Hub   │────HTTP:9001───▶│   Agent Zero     │                  │
│  │  FastAPI     │   (loopback)    │  FastAPI :9001   │                  │
│  │  :8080       │                 │  + daemon mode   │                  │
│  └──────────────┘                 └────────┬─────────┘                  │
│  └──────────────┘                          │                            │
│                                            │ POST /context/store        │
│  External APIs (via Agent Zero):           ▼                            │
│  ┌─────────────────────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Claude · GPT-4o · Gemini   │  │  MCP Server  │  │  Redis (SCS)  │  │
│  │ Grok · Perplexity · Local  │  │  FastAPI     │──▶│  Blackboard   │  │
│  └─────────────────────────────┘  │  :8000       │  │  :6379        │  │
│                                   └──────────────┘  └───────────────┘  │
│                                                             ▲           │
│  ┌───────────────────────────────────────────────────┐      │           │
│  │  Orchestrator (standalone LangGraph, host venv)   │──────┘           │
│  │  orchestrator/router.py  — one-shot execution     │                  │
│  └───────────────────────────────────────────────────┘                  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────┐               │
│  │  Ollama / llama3.2 (Docker, NVIDIA GPU, :11434)      │               │
│  └──────────────────────────────────────────────────────┘               │
│                                                                         │
│  ┌──────────────────────────────────────────────────────┐               │
│  │  SPIRE Identity Layer                                │               │
│  │  SPIRE Server (:8081) ──▶ SPIRE Agent                │               │
│  │  Trust Domain: mpx.sovereign                         │               │
│  └──────────────────────────────────────────────────────┘               │
│                                                                         │
│  ┌────────────────────┐   ┌──────────────────────────────────────────┐  │
│  │  A2A Proxy         │   │  Gateway Sandbox (Docker, kitt_sandbox)  │  │
│  │  nginx :9000       │   │  ubuntu:24.04 + GPU, kitt_sovereign_net  │  │
│  │  Agent Discovery   │   └──────────────────────────────────────────┘  │
│  └────────────────────┘                                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

**Design Principles:**
- Multi-model fan-out: simultaneous dispatch to up to 6 backends (5 external + 1 local)
- Sovereign/air-gap capable: all inference can fall back to Ollama + llama3.2
- Zero-trust identity: SPIFFE SVIDs issued per workload by SPIRE (enforcement pending)
- Blackboard memory: Redis as the single shared state store
- Hardened containers: `no-new-privileges`, non-root users, read-only config mounts
- 3-2-1 backup: automated git sync to local SSD vault (`ssd-vault`) + GitHub (`origin`)
- Governance: ISO 42001-aligned kill switch for immediate cessation

---

## 2. Directory Structure

```
kitt_gateway/
├── .claude/                     # Claude Code project context (not committed to index by Git)
│   ├── CLAUDE.md                # Primary project guidance for Claude Code
│   ├── SYSTEM_BREAKDOWN.md      # This file
│   └── TODO.md                  # Open bugs and incomplete components
├── a2a/
│   ├── agent_zero/              # Agent Zero: source, venv, systemd units, identity card
│   │   ├── agent.py             # Daemon + fan_out() engine + FastAPI HTTP service (:9001)
│   │   ├── kitt-agent.service   # systemd unit — daemon mode (no args)
│   │   ├── kitt-agent-http.service # systemd unit — HTTP service mode (serve, :9001)
│   │   ├── agent-card.json      # A2A identity descriptor
│   │   └── .env                 # API keys (git-ignored)
│   └── registry/                # Gateway capability manifest
├── a2a_proxy/                   # A2A discovery proxy (nginx)
│   └── html/.well-known/        # Public agent-card endpoint
├── config/                      # Read-only kernel/config markers
│   └── kernel_tripwire.txt      # Empty sentinel file; not used by any running process
├── docs/
│   └── intelligence_archive/    # Audit logs and master index
├── governance/
│   ├── kill_switch.sh           # Emergency stop script
│   └── telemetry/               # ATS audit log output
├── hub/                         # KITT Hub: chat UI + model router
│   ├── main.py                  # FastAPI app (port 8080)
│   ├── kitt-hub.service         # systemd unit (installed as kitt-hub.service)
│   ├── requirements.txt         # Pinned hub dependencies
│   ├── static/                  # Frontend assets (index.html, JS, CSS)
│   └── venv/                    # Hub Python venv (git-ignored)
├── inference/                   # Ollama edge inference engine
│   └── models/                  # Model blobs (git-ignored)
├── mcp/                         # MCP Server (FastAPI context API)
│   ├── server.py                # REST shim over Redis
│   ├── Dockerfile               # Container build definition
│   └── docker-compose.yml       # Deploys mpx-mcp-server
├── orchestrator/                # LangGraph workflow router (standalone)
│   └── router.py                # One-shot stateful graph execution
├── scripts/                     # Operational automation scripts
├── security/                    # Firewall baselines
├── shared_context/              # Redis blackboard
│   ├── docker-compose.yaml      # Deploys mpx-shared-context (Redis)
│   └── data/                    # Redis persistence (git-ignored)
├── spire/                       # SPIFFE/SPIRE identity framework
│   ├── agent/                   # SPIRE agent config
│   ├── data/                    # SPIRE runtime data (git-ignored)
│   └── server/                  # SPIRE server config
└── docker-compose.yml           # Root gateway sandbox definition
```

---

## 3. Script & File Purpose Summary

### KITT Hub

| File | Purpose |
|------|---------|
| `hub/main.py` | **KITT Hub** — FastAPI app (port 8080). Serves the chat UI and exposes two endpoints: `POST /chat {prompt, models}` calls `POST http://127.0.0.1:9001/fan_out` on Agent Zero HTTP service (timeout 120s); returns `intent_flagged`, `intent_category`, `intent_score` alongside model responses; returns HTTP 503 `{"error":"Agent Zero unavailable"}` on `RequestException`. `GET /health` probes MCP (:8000) and Ollama (:11434) with 2s timeouts. Env toggle `USE_DIRECT_AGENT_ZERO=true` re-enables legacy `sys.path` import mode. |
| `hub/kitt-hub.service` | systemd unit for the Hub. ExecStart: `python3 main.py` under user `doubl` (main.py invokes uvicorn internally in its `__main__` block). `Restart=always`. Declares `After=network.target docker.service`, `Wants=docker.service`. |
| `hub/requirements.txt` | Pinned Hub dependencies (18 packages): fastapi, uvicorn, requests, python-dotenv, and transitive deps. |
| `hub/static/` | Frontend assets served at `/static`. Contains `index.html` only — a self-contained single-file chat UI (HTML/CSS/JS inline). No separate JS or CSS files. |

### Agent Zero

| File | Purpose |
|------|---------|
| `a2a/agent_zero/agent.py` | **Agent Zero** — Core routing engine, autonomous daemon, and HTTP service. `fan_out(prompt, models)` runs `check_intent()` (llama3.2 pre-screen), dispatches to up to 6 model backends in parallel via `ThreadPoolExecutor`, stores prompt + responses in MCP memory, returns `{"responses": {...}, "intent": {...}}`. Default model list when `None`: `["claude","openai","gemini","grok","perplexity"]`. `run_daemon()` loops every 60s for health telemetry. HTTP serve mode (`python agent.py serve`): FastAPI app on `:9001`, `POST /fan_out` endpoint, singleton `_agent_instance`. `call_gemini()` filters `"thought": true` parts (gemini-2.5-flash thinking traces). |
| `a2a/agent_zero/requirements.txt` | Pinned Agent Zero dependencies (9 packages): requests, python-dotenv, fastapi, uvicorn, pydantic, and transitive deps. |
| `a2a/agent_zero/kitt-agent.service` | systemd unit for the Agent Zero **daemon** (`kitt-agent.service`). Runs `agent.py` (no args) under user `doubl`, `Restart=always`. |
| `a2a/agent_zero/kitt-agent-http.service` | systemd unit for the Agent Zero **HTTP service** (`kitt-agent-http.service`). Runs `agent.py serve` on loopback `:9001`. `EnvironmentFile` loads `.env`. `After=network.target docker.service`. `Restart=on-failure`. |
| `a2a/agent_zero/agent-card.json` | A2A identity descriptor. Declares `agent_id`, SPIFFE ID (`spiffe://mpx.sovereign/agent_zero`), capabilities (`mcp_memory`, `inference_edge`), and security requirements. |
| `a2a/agent_zero/.env` | API keys for all 5 external providers (git-ignored). Loaded at import time via `load_dotenv()`. |
| `a2a/registry/gateway-manifest.json` | Gateway-level capability manifest. Lists capabilities, service ports, and active agent registry. |

### Core Services

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Defines `kitt_sandbox` — Ubuntu 24.04 container with GPU passthrough on `kitt_sovereign_net`. |
| `mcp/server.py` | **MCP Server** — FastAPI REST shim over Redis (port 8000). `POST /context/store` writes agent context (capped at 5 entries per `agent_id`). `GET /context/retrieve` fetches stored context. `GET /health` returns Redis connection status. Lifespan startup (I1 ✅): fetches own X.509-SVID from SPIRE workload API via `spiffe.workloadapi.WorkloadApiClient`; logs SPIFFE ID or fail-open message if socket unavailable. |
| `mcp/docker-compose.yml` | Deploys `mpx-mcp-server` on `kitt_sovereign_net`. Connects to Redis via Docker DNS name `mpx-shared-context`. SPIRE agent socket mounted read-only at `/run/spire/sockets` (I1 ✅). `PYTHONUNBUFFERED=1` set for visible stdout in `docker logs`. |
| `mcp/requirements.txt` | Pinned MCP dependencies (14 packages): `fastapi==0.134.0`, `uvicorn==0.41.0`, `redis==7.2.1`, `spiffe==0.2.5` (py-spiffe, HewlettPackard), and transitive deps. Frozen 2026-03-14. |
| `orchestrator/router.py` | **LangGraph Orchestrator** — One-shot stateful workflow. `AgentState` TypedDict: `messages: Annotated[list[str], operator.add]`. Single node "router" (`process_node`). Reads `mission_status` from Redis, invokes `ChatOllama(model="llama3.2")` (model string is `"llama3.2"`, not `"llama3.2:latest"`), writes actual LLM response back to Redis. Logs 4 event types to ATS audit log. Run manually; not integrated into Hub request path. |
| `shared_context/docker-compose.yaml` | Runs `redis:alpine` as `mpx-shared-context` on `127.0.0.1:6379`, joined to `kitt_sovereign_net`. Persists data via `--save 60 1`. |
| `inference/docker-compose.yaml` | Runs `ollama/ollama:latest` as `mpx-inference-edge` on `127.0.0.1:11434` with 1 NVIDIA GPU reserved. |

### A2A Discovery Proxy

| File | Purpose |
|------|---------|
| `a2a_proxy/docker-compose.yaml` | Runs `nginx:alpine` as `mpx-a2a-proxy` on `0.0.0.0:9000`. Only externally exposed Docker service. |
| `a2a_proxy/html/.well-known/agent-card.json` | Public agent card at `:9000/.well-known/agent-card.json`. Declares SPIFFE ID `spiffe://mpx.sovereign/kitt_node/edge_router`, capabilities, and protocols. |

### SPIRE (Identity Layer)

| File | Purpose |
|------|---------|
| `spire/server/server.conf` | SPIRE Server config. Binds to `0.0.0.0:8081`. Trust domain `mpx.sovereign`. SQLite3 datastore, `join_token` node attestor. |
| `spire/agent/agent.conf` | SPIRE Agent config. Connects to server at `127.0.0.1:8081`. Exposes workload API socket. `insecure_bootstrap: true` (initial setup — not yet hardened). |
| `spire/docker-compose.yaml` | Runs `spire-server` and `spire-agent` (v1.11.0) in `network_mode: host`. Agent has `/var/run/docker.sock` mounted `:ro` (Docker workload attestor) and `pid: host` (required so agent can read `/proc/<pid>/cgroup` for caller containers). |

### Governance & Security

| File | Purpose |
|------|---------|
| `governance/kill_switch.sh` | Emergency cessation (ISO 42001). Stops: `mpx-inference-edge` (Ollama), `mpx-a2a-proxy` (nginx), `kitt-hub` (systemd), `kitt-agent` (systemd). Redis and SPIRE remain running. |
| `governance/telemetry/ats_audit.log` | Append-only audit log from `orchestrator/router.py`. JSON events: `intent_received`, `memory_read`, `inference_complete`, `memory_write`. |
| `security/firewall_baseline_v2.txt` | Active UFW baseline: SSH restricted to LAN (`192.168.1.0/24`). Default deny inbound. |

### Automation

| File | Purpose |
|------|---------|
| `scripts/sync_kitt.sh` | **3-2-1 Backup** — Stages, commits with timestamp, pushes to `ssd-vault` (local SSD at `/mnt/kitt-backup`) then `origin` (GitHub). |

---

## 4. Environment Variables & Configuration Reference

### API Keys (a2a/agent_zero/.env — git-ignored)

| Variable | Provider | Used in |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Anthropic Claude | `agent.py::call_claude()` |
| `OPENAI_API_KEY` | OpenAI GPT-4o | `agent.py::call_openai()` |
| `GEMINI_API_KEY` | Google Gemini | `agent.py::call_gemini()` |
| `GROK_API_KEY` | xAI Grok | `agent.py::call_grok()` |
| `PERPLEXITY_API_KEY` | Perplexity Sonar | `agent.py::call_perplexity()` |

### Hard-coded Constants

| Constant | Value | Location |
|----------|-------|----------|
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | `agent.py:14` |
| `MCP_URL` | `http://localhost:8000` | `agent.py:15` |
| `MODEL` | `llama3.2:latest` | `agent.py:16` |
| `AGENT_ID` | `agent_zero` | `agent.py:17` |
| `HEARTBEAT_INTERVAL` | `60` (seconds) | `agent.py:18` |
| `AGENT_URL` | `http://127.0.0.1:9001` | `hub/main.py` |
| `USE_DIRECT_AGENT_ZERO` | `false` (default) | `hub/main.py` env toggle |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | `orchestrator/router.py:21` |
| `SPIRE_SOCKET` | `/run/spire/sockets/agent.sock` | `mcp/server.py:12` — active; used in lifespan SVID fetch (I1 ✅) |
| `ATS_LOG_FILE` | `~/kitt_gateway/governance/telemetry/ats_audit.log` | `orchestrator/router.py:11` |
| `PYTHONUNBUFFERED` | `1` | `kitt-agent.service`; `mcp/docker-compose.yml` (added 2026-03-14) |

### SPIRE Configuration

| Parameter | Value | File |
|-----------|-------|------|
| `trust_domain` | `mpx.sovereign` | `spire/server/server.conf`, `spire/agent/agent.conf` |
| `bind_port` (server) | `8081` | `spire/server/server.conf` |
| `socket_path` (agent) | `/run/spire/sockets/agent.sock` | `spire/agent/agent.conf` |
| `join_token` | `fc0aa621-...` (consumed; emergency re-attest only) | `spire/agent/agent.conf` |
| `insecure_bootstrap` | `false` ✅ | `spire/agent/agent.conf` |
| `trust_bundle_path` | `/run/spire/config/bootstrap.crt` | `spire/agent/agent.conf` |
| `ca_key_type` | `rsa-2048` | `spire/server/server.conf` |

### Docker Network

| Parameter | Value | Notes |
|-----------|-------|-------|
| `kitt_sovereign_net` | External | Pre-create: `docker network create kitt_sovereign_net` |
| Redis bind | `127.0.0.1:6379` | Loopback only |
| Ollama bind | `127.0.0.1:11434` | Loopback only |
| MCP Server | `127.0.0.1:8000` | Host-bound; Agent Zero reaches via `localhost` |
| Hub | `0.0.0.0:8080` | LAN-accessible chat UI |
| A2A Proxy | `0.0.0.0:9000` | Externally accessible |
| SPIRE Server | `8081` | Host network mode |

### Git Remotes

| Remote | Path | Purpose |
|--------|------|---------|
| `origin` | `github.com:Double00kevin/kitt_gateway.git` | GitHub cloud backup |
| `ssd-vault` | `/mnt/kitt-backup/kitt_gateway.git` | Local SSD backup (auto-mounts via fstab) |

---

## 5. Component Interaction Map

### Data Flow: Primary Request (Browser → Hub → fan_out → APIs)

```
Browser  POST /chat {prompt, models}
    │
    └──▶ hub/main.py (kitt-hub.service, :8080)
              │
              └──▶ POST http://127.0.0.1:9001/fan_out  (kitt-agent-http.service)
                        │
                        └──▶ AgentZero.fan_out(prompt, models)   [ThreadPoolExecutor]
                        │
                        ├──▶ retrieve_context()  ──▶ GET MCP /context/retrieve
                        ├──▶ store_context(prompt)──▶ POST MCP /context/store
                        │
                        ├──▶ call_claude()    ──▶ api.anthropic.com  (claude-sonnet-4-*)
                        ├──▶ call_openai()    ──▶ api.openai.com     (gpt-4o)
                        ├──▶ call_gemini()    ──▶ generativelanguage.googleapis.com
                        ├──▶ call_grok()      ──▶ api.x.ai           (grok-3-latest)
                        ├──▶ call_perplexity()──▶ api.perplexity.ai  (sonar-pro)
                        └──▶ call_local()     ──▶ Ollama :11434       (llama3.2)
                                  │
                                  └──▶ store_context(each response)
                                  └──▶ return {model: response} dict to Hub
                                  └──▶ Hub returns JSON to browser
```

### Data Flow: Agent Zero Health Tick (every 60s)

```
kitt-agent.service (systemd)
    │
    └──▶ agent.py::run_daemon()
              │
              └──▶ system_health_check()
                        ├──▶ subprocess("uptime")          ← Host OS
                        ├──▶ subprocess("docker ps -q")    ← Docker daemon
                        ├──▶ GET http://localhost:8000/health  ← MCP Server
                        └──▶ GET http://localhost:11434/api/tags ← Ollama
                                  │
                                  ├──▶ STATUS: {...} log   → systemd journal
                                  └──▶ POST MCP /context/store (agent_id="kitt_status")
                                                            → Redis blackboard
                        (sleeps 60s, repeats)
```

### Data Flow: Orchestrator (LangGraph Router — standalone)

```
orchestrator/router.py (invoked directly, not part of Hub request path)
    │
    ├──▶ Redis.get("mission_status")      ← shared_context (Redis :6379)
    │         └── injects context into system prompt
    │
    ├──▶ ChatOllama.invoke(prompt)         ← mpx-inference-edge (Ollama :11434)
    │         └── returns LLM response
    │
    ├──▶ Redis.set("mission_status", response.content) → Redis :6379
    │
    └──▶ ATS audit log entry               → governance/telemetry/ats_audit.log
```

### Data Flow: MCP Server (Context API)

```
Any Agent / Client
    │
    ├──▶ POST /context/store  {agent_id, content}
    │         └──▶ Redis.lpush("agent:<id>:context", content)
    │               Redis.ltrim(key, 0, 4)   ← keeps last 5 messages
    │
    ├──▶ GET /context/retrieve?agent_id=<id>
    │         └──▶ Redis.lrange("agent:<id>:context", 0, 4)
    │
    └──▶ GET /health
              └──▶ Redis ping → {"status":"ok","redis_connection":"active"}

  Active agent_id namespaces:
    agent:agent_zero:context   — conversation history (Hub/fan_out)
    agent:kitt_status:context  — system health reports (daemon tick)
```

### Data Flow: Emergency Kill Switch

```
operator$ bash governance/kill_switch.sh
    │
    ├──▶ docker stop mpx-inference-edge    ← halts Ollama (inference)
    ├──▶ docker stop mpx-a2a-proxy         ← halts nginx (A2A comms)
    ├──▶ systemctl stop kitt-hub           ← halts Hub (chat UI)
    └──▶ systemctl stop kitt-agent         ← halts Agent Zero daemon

    [Redis + SPIRE remain running — memory and identity preserved]
```

### Full Port Map

```
Port   Protocol   Bind            Service                      Exposure
────   ────────   ─────────────   ──────────────────────────   ──────────────
22     TCP        host            SSH (OpenSSH)                LAN only
6379   TCP        127.0.0.1       Redis (SCS/blackboard)       Loopback only
8000   TCP        127.0.0.1       MCP Server (FastAPI)         Loopback only
8080   TCP        0.0.0.0         KITT Hub (chat UI/router)    LAN-accessible
8081   TCP        0.0.0.0 (host)  SPIRE Server                 Host network
9000   TCP        0.0.0.0         A2A Proxy (nginx)            Public
9001   TCP        127.0.0.1       Agent Zero HTTP service      Loopback only
11434  TCP        127.0.0.1       Ollama inference             Loopback only
50080  TCP        0.0.0.0         Stock Agent Zero (Docker)    LAN (separate)
```

### Docker Compose Service Registry

```
Compose File                       Container Name        Image                               Status
─────────────────────────────────  ────────────────────  ──────────────────────────────────  ──────
shared_context/docker-compose.yaml mpx-shared-context    redis:alpine                        up
inference/docker-compose.yaml      mpx-inference-edge    ollama/ollama:latest                up
mcp/docker-compose.yml             mpx-mcp-server        python:3.12-slim (built)            up
a2a_proxy/docker-compose.yaml      mpx-a2a-proxy         nginx:alpine                        down
spire/docker-compose.yaml          spire-server          ghcr.io/spiffe/spire-server:1.11.0  up
spire/docker-compose.yaml          spire-agent           ghcr.io/spiffe/spire-agent:1.11.0   up
docker-compose.yml                 kitt_sandbox          ubuntu:24.04                        down
```

### systemd Services

```
Service                   Unit File                                    Status
────────────────────────  ───────────────────────────────────────────  ──────
kitt-hub.service          hub/kitt-hub.service                         active
kitt-agent.service        a2a/agent_zero/kitt-agent.service            active
kitt-agent-http.service   a2a/agent_zero/kitt-agent-http.service       active
```

---

## 6. Security Notes

- **Firewall (v2 baseline):** Default deny inbound. SSH restricted to `192.168.1.0/24`. Port 8080 (Hub) is LAN-accessible. Port 9000 (A2A nginx) is public.
- **SPIRE bootstrap hardened (I7 ✅):** `insecure_bootstrap = false`. Server trust bundle pinned at `spire/agent/bootstrap.crt` (mounted into agent at `/run/spire/config/bootstrap.crt`; referenced via `trust_bundle_path`). Agent verifies server TLS on every connection. Join token rotated 2026-03-13; current token (`fc0aa621-...`) is single-use/consumed. To re-attest after data dir wipe: `docker exec spire-server /opt/spire/bin/spire-server token generate -spiffeID spiffe://mpx.sovereign/spire-agent -ttl 3600`, update `agent.conf`, restart agent.
- **`.gitignore`** excludes: `spire/data/`, `security/secrets/`, `*.key`, `*.pem`, `*.sock`, `*.sqlite3`, `shared_context/data/`, model blobs, Python caches, `.env`, `.claude/settings.local.json`.
- **API keys** live in `a2a/agent_zero/.env` (git-ignored). Hub inherits them at import time via `load_dotenv()`.
- **PQC intent:** `agent-card.json` declares `ML-KEM-768` — not yet implemented. (I3 — open)
- **SVID fetch at startup (I1 ✅, workload entry registered ✅):** `mcp/server.py` lifespan fetches MCP Server's own X.509-SVID from SPIRE workload API using `spiffe.workloadapi.WorkloadApiClient(socket_path="unix:///run/spire/sockets/agent.sock")`. Fail-open: any exception logs `[SPIRE] SVID fetch failed (fail-open): <reason>` and MCP continues serving. Workload entry registered 2026-03-14: entry ID `073f4fd3-ebf5-45dc-902c-feabf9459805`, SPIFFE ID `spiffe://mpx.sovereign/mcp`, selectors `docker:label:com.docker.compose.project:mcp` + `docker:label:com.docker.compose.service:mcp-server`, parentID `spiffe://mpx.sovereign/spire/agent/join_token/fc0aa621-228a-4667-97a7-a63e0f6b73cc`. MCP now logs `[SPIRE] MCP Server SVID: spiffe://mpx.sovereign/mcp` on startup. Socket mounted `:ro` into container. Note: if agent re-attests with a new join token, parentID must be updated.
- **Intent gate (I2 ✅):** `check_intent()` pre-screens every prompt via llama3.2 before `fan_out()` fires. Flag-only (never blocks). Categories: `none`, `prompt_injection`, `jailbreak`, `unsafe`. Flagged events logged to `ats_audit.log` (prompt hash only), MCP `kitt_status`, and systemd journal. Hub returns `intent_flagged`, `intent_category`, `intent_score` in every `/chat` response.
- **Hub–Agent decoupling (A1 ✅):** Hub calls Agent Zero over `POST http://127.0.0.1:9001/fan_out` (loopback HTTP). No shared venv or `sys.path` injection. Hub returns 503 if Agent Zero HTTP service is down. Rollback toggle: `USE_DIRECT_AGENT_ZERO=true`.
- **All containers** use `no-new-privileges: true`. MCP Server runs as non-root `mcp_user`.
