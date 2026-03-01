# KITT Sovereign Gateway — System Breakdown

**Updated:** 2026-03-01
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
│        │                                     │                          │
│        │  Browser / LAN client               │  60s health tick         │
│        ▼                                     ▼                          │
│  ┌──────────────┐    fan_out()    ┌──────────────────┐                  │
│  │   KITT Hub   │────────────────▶│   Agent Zero     │                  │
│  │  FastAPI     │                 │   (daemon)       │                  │
│  │  :8080       │                 └────────┬─────────┘                  │
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
│   ├── agent_zero/              # Agent Zero: source, venv, systemd unit, identity card
│   │   ├── agent.py             # Primary daemon + fan_out() routing engine
│   │   ├── kitt-agent.service   # systemd unit (installed as kitt-agent.service)
│   │   ├── agent-card.json      # A2A identity descriptor
│   │   └── .env                 # API keys (git-ignored)
│   └── registry/                # Gateway capability manifest
├── a2a_proxy/                   # A2A discovery proxy (nginx)
│   └── html/.well-known/        # Public agent-card endpoint
├── config/                      # Read-only kernel/config markers
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
| `hub/main.py` | **KITT Hub** — FastAPI app (port 8080). Serves the chat UI and exposes two endpoints: `POST /chat {prompt, models}` fans out to selected models via Agent Zero's `fan_out()`; `GET /health` probes MCP (:8000) and Ollama (:11434) with 2s timeouts, returns `{"status":"ok"\|"degraded","checks":{...}}` with HTTP 200/503. Imports `AgentZero` directly via `sys.path` injection. |
| `hub/kitt-hub.service` | systemd unit for the Hub. Runs `uvicorn hub/main.py` under user `doubl`, `Restart=always`. Starts after `network.target`. |
| `hub/requirements.txt` | Pinned Hub dependencies (18 packages): fastapi, uvicorn, requests, python-dotenv, and transitive deps. |
| `hub/static/` | Frontend assets served at `/static`. Contains `index.html` with the chat UI. |

### Agent Zero

| File | Purpose |
|------|---------|
| `a2a/agent_zero/agent.py` | **Agent Zero** — Core routing engine and autonomous daemon. `fan_out(prompt, models)` dispatches to up to 6 model backends in parallel via `ThreadPoolExecutor`, stores prompt + responses in MCP memory, and returns `{model: response}` dict. `run_daemon()` loops every 60s: runs `system_health_check()` (probes MCP + Ollama, captures uptime/container count), logs structured JSON status to systemd journal, and writes a health report to MCP under `agent_id="kitt_status"`. |
| `a2a/agent_zero/kitt-agent.service` | systemd unit for the Agent Zero daemon (`kitt-agent.service`). Runs `agent.py` under user `doubl`, `Restart=always`. |
| `a2a/agent_zero/agent-card.json` | A2A identity descriptor. Declares `agent_id`, SPIFFE ID (`spiffe://mpx.sovereign/agent_zero`), capabilities (`mcp_memory`, `inference_edge`), and security requirements. |
| `a2a/agent_zero/.env` | API keys for all 5 external providers (git-ignored). Loaded at import time via `load_dotenv()`. |
| `a2a/registry/gateway-manifest.json` | Gateway-level capability manifest. Lists capabilities, service ports, and active agent registry. |

### Core Services

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Defines `kitt_sandbox` — Ubuntu 24.04 container with GPU passthrough on `kitt_sovereign_net`. |
| `mcp/server.py` | **MCP Server** — FastAPI REST shim over Redis (port 8000). `POST /context/store` writes agent context (capped at 5 entries per `agent_id`). `GET /context/retrieve` fetches stored context. `GET /health` returns Redis connection status. |
| `mcp/docker-compose.yml` | Deploys `mpx-mcp-server` on `kitt_sovereign_net`. Connects to Redis via Docker DNS name `mpx-shared-context`. |
| `orchestrator/router.py` | **LangGraph Orchestrator** — One-shot stateful workflow. Reads `mission_status` from Redis, invokes llama3.2 via `ChatOllama`, writes actual LLM response back to Redis. Logs events to ATS audit log. Run manually; not integrated into Hub request path. |
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
| `spire/docker-compose.yaml` | Runs `spire-server` and `spire-agent` (v1.11.0) in `network_mode: host`. |

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
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | `agent.py:13` |
| `MCP_URL` | `http://localhost:8000` | `agent.py:14` |
| `MODEL` | `llama3.2:latest` | `agent.py:15` |
| `AGENT_ID` | `agent_zero` | `agent.py:16` |
| `HEARTBEAT_INTERVAL` | `60` (seconds) | `agent.py:17` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | `orchestrator/router.py:21` |
| `SPIRE_SOCKET` | `/run/spire/sockets/agent.sock` | `mcp/server.py:9` (reserved) |
| `ATS_LOG_FILE` | `~/kitt_gateway/governance/telemetry/ats_audit.log` | `orchestrator/router.py:11` |
| `PYTHONUNBUFFERED` | `1` | `kitt-agent.service`, `kitt-hub.service` |

### SPIRE Configuration

| Parameter | Value | File |
|-----------|-------|------|
| `trust_domain` | `mpx.sovereign` | `spire/server/server.conf`, `spire/agent/agent.conf` |
| `bind_port` (server) | `8081` | `spire/server/server.conf` |
| `socket_path` (agent) | `/run/spire/sockets/agent.sock` | `spire/agent/agent.conf` |
| `join_token` | `REDACTED_SPIRE_TOKEN_1` | `spire/agent/agent.conf` ⚠️ rotate |
| `insecure_bootstrap` | `true` | `spire/agent/agent.conf` ⚠️ disable after attestation |
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
spire/docker-compose.yaml          spire-server          ghcr.io/spiffe/spire-server:1.11.0  down
spire/docker-compose.yaml          spire-agent           ghcr.io/spiffe/spire-agent:1.11.0   down
docker-compose.yml                 kitt_sandbox          ubuntu:24.04                        down
```

### systemd Services

```
Service             Unit File                            Status
──────────────────  ───────────────────────────────────  ──────
kitt-hub.service    hub/kitt-hub.service                 active
kitt-agent.service  a2a/agent_zero/kitt-agent.service    active
```

---

## 6. Security Notes

- **Firewall (v2 baseline):** Default deny inbound. SSH restricted to `192.168.1.0/24`. Port 8080 (Hub) is LAN-accessible. Port 9000 (A2A nginx) is public.
- **SPIRE join token** (`REDACTED_SPIRE_TOKEN_1`) is stored in plaintext in `spire/agent/agent.conf`. Rotate after first attestation. (I7 — open)
- **`insecure_bootstrap: true`** in SPIRE agent — disable after the trust bundle is established. (I7 — open)
- **`.gitignore`** excludes: `spire/data/`, `security/secrets/`, `*.key`, `*.pem`, `*.sock`, `*.sqlite3`, `shared_context/data/`, model blobs, Python caches, `.env`, `.claude/settings.local.json`.
- **API keys** live in `a2a/agent_zero/.env` (git-ignored). Hub inherits them at import time via `load_dotenv()`.
- **PQC intent:** `agent-card.json` declares `ML-KEM-768` — not yet implemented. (I3 — open)
- **Intent gate:** `agent-card.json` declares `intent_gate_required: true` — no pre-call validation exists. Any string sent to `POST /chat` is forwarded verbatim. (I2 — open)
- **All containers** use `no-new-privileges: true`. MCP Server runs as non-root `mcp_user`.
