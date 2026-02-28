# KITT Sovereign Gateway — System Breakdown

**Generated:** 2026-02-27
**Architecture Codename:** MadProjx-v1
**Gateway ID:** KITT-Sovereign-Gateway v1.1.0

---

## 1. High-Level Architecture Overview

KITT Gateway is a **local-first, sovereign AI infrastructure** designed to run autonomous agents entirely on self-hosted hardware. No external AI APIs are required for inference. The design follows a "blackboard" pattern: all components share state through a central Redis store, each component writes/reads to a common memory space, and cryptographic identity is enforced via SPIFFE/SPIRE.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HOST MACHINE (Linux)                         │
│                                                                     │
│  [systemd: agent-zero.service]          [UFW Firewall]              │
│        │                                  Port 22 (LAN only)       │
│        │                                  Port 9000 (public)        │
│        ▼                                                            │
│  ┌─────────────┐     ┌──────────────┐     ┌────────────────────┐   │
│  │  Agent Zero │────▶│  MCP Server  │────▶│   Redis (SCS)      │   │
│  │  (daemon)   │     │  FastAPI     │     │   Blackboard       │   │
│  └──────┬──────┘     │  :8000       │     │   127.0.0.1:6379   │   │
│         │            └──────────────┘     └────────────────────┘   │
│         │                  ▲                       ▲               │
│         │                  │                       │               │
│         ▼                  │                       │               │
│  ┌─────────────┐           │               ┌───────────────────┐   │
│  │  Ollama     │           │               │  Orchestrator     │   │
│  │  Inference  │◀──────────┘               │  (LangGraph)      │   │
│  │  127.0.0.1  │                           │  router.py        │   │
│  │  :11434     │                           └───────────────────┘   │
│  │  llama3.2   │                                                    │
│  │  NVIDIA GPU │                                                    │
│  └─────────────┘                                                    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  SPIRE Identity Layer                                        │   │
│  │  SPIRE Server (:8081) ──▶ SPIRE Agent ──▶ /run/spire/sockets│   │
│  │  Trust Domain: mpx.sovereign                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌───────────────────┐    ┌─────────────────────────────────────┐  │
│  │  A2A Proxy        │    │  Gateway Sandbox (Docker)           │  │
│  │  nginx :9000      │    │  ubuntu:24.04 + GPU                 │  │
│  │  Agent Discovery  │    │  kitt_sovereign_net                 │  │
│  └───────────────────┘    └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

**Design Principles:**
- Sovereign/air-gap capable: all inference is local (Ollama + llama3.2)
- Zero-trust identity: SPIFFE SVIDs issued per workload by SPIRE
- Blackboard memory: Redis as the single shared state store
- Hardened containers: `no-new-privileges`, non-root users, read-only config mounts
- 3-2-1 backup: automated git sync to local SSD vault + GitHub
- Governance: ISO 42001-aligned kill switch for immediate cessation

---

## 2. Directory Structure

```
kitt_gateway/
├── a2a/
│   ├── agent_zero/          # Agent Zero source, systemd unit, identity card
│   └── registry/            # Gateway capability manifest
├── a2a_proxy/               # A2A discovery proxy (nginx)
│   └── html/.well-known/    # Public agent-card endpoint
├── config/                  # Read-only kernel/config markers
├── docs/
│   └── intelligence_archive/ # Audit logs and master index
├── governance/
│   ├── kill_switch.sh       # Emergency stop script
│   └── telemetry/           # ATS audit log output
├── inference/               # Ollama edge inference engine
│   └── models/              # Model blobs (git-ignored)
├── mcp/                     # MCP Server (FastAPI context API)
├── orchestrator/            # LangGraph workflow router
├── scripts/                 # Operational automation scripts
├── security/                # Firewall baselines
├── shared_context/          # Redis blackboard + ledger
│   └── data/                # Redis persistence (git-ignored)
├── spire/                   # SPIFFE/SPIRE identity framework
│   ├── agent/               # SPIRE agent config
│   ├── data/                # SPIRE runtime data (git-ignored)
│   └── server/              # SPIRE server config
└── docker-compose.yml       # Root gateway sandbox definition
```

---

## 3. Script & File Purpose Summary

### Core Services

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Defines `kitt_sandbox` — an Ubuntu 24.04 container with GPU passthrough, read-only config/MCP mounts, read-write shared_context and logs. Attaches to external `kitt_sovereign_net`. The primary isolated execution environment. |
| `mcp/server.py` | **MCP Server** — FastAPI application (port 8000). Provides two REST endpoints: `POST /context/store` (writes agent context into Redis, retaining the last 5 messages) and `GET /context/retrieve` (fetches stored context by `agent_id`). Health check at `GET /health`. |
| `mcp/Dockerfile` | Builds the MCP Server container. Uses `python:3.12-slim`, runs as non-root user `mcp_user`, exposes port 8000, starts with uvicorn. |
| `mcp/requirements.txt` | MCP Server Python dependencies: `fastapi`, `uvicorn`, `redis`. |
| `orchestrator/router.py` | **LangGraph Orchestrator** — Defines a single-node stateful workflow using `StateGraph`. Reads `mission_status` from Redis, injects it as context into a Llama 3.2 prompt via `ChatOllama`, writes updated state back to Redis. Logs all actions to the ATS audit log with SPIFFE agent IDs. |
| `shared_context/docker-compose.yaml` | Runs `redis:alpine` as `mpx-shared-context` on `127.0.0.1:6379`. Persists data via `--save 60 1`. Bind-mounted to `./data`. |
| `shared_context/ledger.json` | Flat JSON ledger tracking `gateway_status`, `active_agents`, and `shared_memory`. Currently shows gateway ONLINE with no active agents in the ledger. |
| `shared_context/probe.txt` | Static marker confirming the shared memory pipeline is active. |
| `inference/docker-compose.yaml` | Runs `ollama/ollama:latest` as `mpx-inference-edge` on `127.0.0.1:11434`. Mounts `./models` for model storage. Reserves 1 NVIDIA GPU. |

### Agent Zero

| File | Purpose |
|------|---------|
| `a2a/agent_zero/agent.py` | **Agent Zero Daemon** — Primary autonomous actor. Runs an infinite loop that: (1) gathers real telemetry (`uptime`, active Docker container count via `docker ps`), (2) logs a heartbeat with that telemetry, (3) sleeps 60 seconds. Connects to Ollama `:11434` and MCP Server `:8000` (configured but not actively called in current implementation). |
| `a2a/agent_zero/agent-zero.service` | Systemd unit file. Runs `agent.py` under user `doubl` with `Restart=always`. Starts after `network.target` and `docker.service`. Logs to systemd journal. |
| `a2a/agent_zero/agent-card.json` | Agent identity descriptor (A2A protocol format). Declares Agent Zero's `agent_id`, role ("Primary Autonomous Actor"), SPIFFE ID, capabilities (`mcp_memory`, `inference_edge`), and security requirements (`intent_gate_required: true`, PQC standard ML-KEM-768). |
| `a2a/agent_zero/requirements.txt` | Agent Zero Python dependencies: `certifi`, `charset-normalizer`, `idna`, `python-dotenv`, `requests`, `urllib3`. |
| `a2a/registry/gateway-manifest.json` | Gateway-level capability manifest. Lists the gateway's capabilities (SPIRE identity, Redis/MCP context storage, inference routing), service ports (9000 RPC, 8000 context), and the registry of active agents. |

### A2A Discovery Proxy

| File | Purpose |
|------|---------|
| `a2a_proxy/docker-compose.yaml` | Runs `nginx:alpine` as `mpx-a2a-proxy` on `0.0.0.0:9000`. Serves static HTML from `./html`. This is the only externally exposed service. |
| `a2a_proxy/html/.well-known/agent-card.json` | Publicly accessible agent card served at `http://<host>:9000/.well-known/agent-card.json`. Declares the KITT Edge Inference Router's SPIFFE ID, capabilities (PII masking, intent classification, local routing), and protocols (A2A-JSON-RPC-2.0, CA-MCP). |

### SPIRE (Identity Layer)

| File | Purpose |
|------|---------|
| `spire/server/server.conf` | SPIRE Server configuration. Binds to `0.0.0.0:8081`. Trust domain `mpx.sovereign`. Uses SQLite3 datastore and disk-backed key manager. NodeAttestor is `join_token`. |
| `spire/agent/agent.conf` | SPIRE Agent configuration. Connects to SPIRE Server at `127.0.0.1:8081`. Exposes workload API socket at `/run/spire/sockets/agent.sock`. Uses `join_token` attestation and Docker workload attestor. `insecure_bootstrap: true` (initial setup). |
| `spire/docker-compose.yaml` | Runs both `spire-server` (v1.11.0) and `spire-agent` (v1.11.0) containers in `network_mode: host`. Server config mounted read-only; data directories mounted read-write. Agent mounts the host socket directory. |

### Governance & Security

| File | Purpose |
|------|---------|
| `governance/kill_switch.sh` | Emergency cessation script (ISO 42001 compliance). Stops `mpx-inference-edge` (Ollama) and `mpx-a2a-proxy` (nginx). Note: leaves Redis and SPIRE intact — "Memory and Identity layers remain intact." |
| `governance/telemetry/ats_audit.log` | Append-only audit log written by `orchestrator/router.py`. Each entry is a timestamped JSON event with `agent_id`, `action`, and metadata. Events include: `intent_received`, `memory_read`, `inference_complete`, `memory_write`. |
| `security/firewall_baseline_v1.txt` | UFW snapshot (v1): SSH open to all (IPv4 + IPv6). Default deny inbound. |
| `security/firewall_baseline_v2.txt` | UFW snapshot (v2, hardened): SSH restricted to LAN (`192.168.1.0/24` only). Default deny inbound. Current enforced baseline. |
| `config/kernel_tripwire.txt` | Kernel/config integrity marker file (mounted read-only into gateway-sandbox). |

### Automation

| File | Purpose |
|------|---------|
| `scripts/sync_kitt.sh` | **3-2-1 Backup Script** — Stages all changes (`git add .`), commits with a timestamp, pushes to `ssd-vault` remote (local SSD), then pushes to `origin` (GitHub). Triggered on-demand or via cron. |

### Documentation

| File | Purpose |
|------|---------|
| `docs/intelligence_archive/00_MASTER_INDEX.md` | Master index of all intelligence archive entries. Links to audit reports by date. |
| `docs/intelligence_archive/2026-02-24_System_Audit_Baseline.md` | Phase 1-6 baseline audit. Verifies presence and correctness of: backup script, `.gitignore`, SPIRE setup, Docker infrastructure, Redis configuration, and documentation structure. |

---

## 4. Environment Variables & Configuration Reference

### Hard-coded Constants (no `.env` file present)

These values are embedded directly in source files. A `.env` file is git-ignored but not yet implemented.

| Variable / Constant | Value | Location | Description |
|---------------------|-------|----------|-------------|
| `REDIS_HOST` | `localhost` / `127.0.0.1` | `mcp/server.py:7`, `orchestrator/router.py:15` | Redis bind address |
| `REDIS_PORT` | `6379` | `mcp/server.py:8`, `orchestrator/router.py:15` | Redis port |
| `SPIRE_SOCKET` | `/run/spire/sockets/agent.sock` | `mcp/server.py:9` | SPIRE workload API socket (reserved for future use) |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | `a2a/agent_zero/agent.py:9` | Ollama generation endpoint |
| `MCP_URL` | `http://localhost:8000` | `a2a/agent_zero/agent.py:10` | MCP Server base URL |
| `MODEL` | `llama3.2:latest` | `a2a/agent_zero/agent.py:11` | Ollama model name |
| `AGENT_ID` | `agent_zero` | `a2a/agent_zero/agent.py:12` | Agent's Redis namespace key prefix |
| `HEARTBEAT_INTERVAL` | `60` (seconds) | `a2a/agent_zero/agent.py:13` | Agent Zero polling interval |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | `orchestrator/router.py:21` | Ollama URL for LangChain ChatOllama |
| `OLLAMA_MODEL` | `llama3.2` | `orchestrator/router.py:21` | Model for orchestrator |
| `ATS_LOG_FILE` | `~/kitt_gateway/governance/telemetry/ats_audit.log` | `orchestrator/router.py:11` | Audit log path |
| `PYTHONUNBUFFERED` | `1` | `a2a/agent_zero/agent-zero.service:14` | Force unbuffered stdout for systemd journal |

### SPIRE Configuration

| Parameter | Value | File |
|-----------|-------|------|
| `trust_domain` | `mpx.sovereign` | `spire/server/server.conf`, `spire/agent/agent.conf` |
| `bind_port` (server) | `8081` | `spire/server/server.conf` |
| `socket_path` (agent) | `/run/spire/sockets/agent.sock` | `spire/agent/agent.conf` |
| `join_token` | `6087b957-918f-4eed-a0da-813dcf887f10` | `spire/agent/agent.conf` |
| `insecure_bootstrap` | `true` | `spire/agent/agent.conf` |
| `ca_key_type` | `rsa-2048` | `spire/server/server.conf` |
| `database_type` | `sqlite3` | `spire/server/server.conf` |

### Docker Network

| Parameter | Value | Notes |
|-----------|-------|-------|
| `kitt_sovereign_net` | External | Must be pre-created: `docker network create kitt_sovereign_net` |
| Redis bind | `127.0.0.1:6379` | Loopback only — no external exposure |
| Ollama bind | `127.0.0.1:11434` | Loopback only — no external exposure |
| MCP Server port | `8000` | Internal to kitt_sovereign_net |
| A2A Proxy port | `0.0.0.0:9000` | Externally accessible |
| SPIRE Server port | `8081` | Host network mode |

### Git Remotes (scripts/sync_kitt.sh)

| Remote | Purpose |
|--------|---------|
| `ssd-vault` | Local physical SSD backup |
| `origin` | GitHub cloud backup |

---

## 5. Component Interaction Map

### Data Flow: Agent Zero Heartbeat Loop

```
agent-zero.service (systemd)
    │
    └──▶ agent.py::run_daemon()
              │
              ├──▶ subprocess("uptime")          ← Host OS
              ├──▶ subprocess("docker ps -q")     ← Docker daemon
              │
              └──▶ HEARTBEAT log to stdout        → systemd journal
                   (sleeps 60s, repeats)
```

*Note: OLLAMA_URL and MCP_URL are configured but calls are not yet wired into the daemon loop.*

### Data Flow: Orchestrator (LangGraph Router)

```
orchestrator/router.py (invoked directly)
    │
    ├──▶ Redis.get("mission_status")     ← shared_context (Redis :6379)
    │         │
    │         └── injects context into system prompt
    │
    ├──▶ ChatOllama.invoke(prompt)       ← inference-edge (Ollama :11434)
    │         │
    │         └── returns LLM response
    │
    ├──▶ Redis.set("mission_status", ...) → shared_context (Redis :6379)
    │
    └──▶ ATS audit log entry             → governance/telemetry/ats_audit.log
```

### Data Flow: MCP Server (Context API)

```
Any Agent / Client
    │
    ├──▶ POST /context/store  {agent_id, content}
    │         │
    │         └──▶ Redis.lpush("agent:<id>:context", content)
    │               Redis.ltrim(key, 0, 4)   ← keeps last 5 messages
    │
    └──▶ GET /context/retrieve?agent_id=<id>
              │
              └──▶ Redis.lrange("agent:<id>:context", 0, 4)
                        └── returns message list
```

### Data Flow: A2A Agent Discovery

```
External Agent / Browser
    │
    └──▶ HTTP GET :9000/.well-known/agent-card.json
              │
              └──▶ nginx (mpx-a2a-proxy)
                        │
                        └── serves a2a_proxy/html/.well-known/agent-card.json
                              (declares SPIFFE ID, capabilities, endpoints)
```

### Data Flow: SPIRE Identity Issuance

```
SPIRE Server (spire-server container, host network, :8081)
    │
    │  [join_token attestation]
    │
    └──▶ SPIRE Agent (spire-agent container, host network)
              │
              └── exposes workload API at:
                    /home/doubl/kitt_gateway/spire/sockets/agent.sock
                    (mounted into kitt_sandbox as /run/spire/sockets:ro)
                              │
                              └──▶ Workload (MCP Server, future)
                                    requests SPIFFE SVID certificate
```

### Data Flow: Emergency Kill Switch

```
operator$ bash governance/kill_switch.sh
    │
    ├──▶ docker stop mpx-inference-edge   ← halts Ollama (inference)
    └──▶ docker stop mpx-a2a-proxy        ← halts nginx (A2A comms)

    [Redis + SPIRE remain running — memory and identity preserved]
```

### Full Port Map

```
Port   Protocol   Bind            Service               Exposure
────   ────────   ─────────────   ───────────────────   ──────────────
22     TCP        host            SSH (OpenSSH)         LAN only (v2)
6379   TCP        127.0.0.1       Redis (SCS/blackboard) Loopback only
8000   TCP        0.0.0.0         MCP Server (FastAPI)  kitt_sovereign_net
8081   TCP        0.0.0.0 (host)  SPIRE Server          Host network
9000   TCP        0.0.0.0         A2A Proxy (nginx)     Public
11434  TCP        127.0.0.1       Ollama inference      Loopback only
```

### Docker Compose Service Registry

```
Compose File                      Container Name        Image
────────────────────────────────  ────────────────────  ──────────────────────
docker-compose.yml                kitt_sandbox          ubuntu:24.04
shared_context/docker-compose.yaml mpx-shared-context   redis:alpine
inference/docker-compose.yaml     mpx-inference-edge    ollama/ollama:latest
a2a_proxy/docker-compose.yaml     mpx-a2a-proxy         nginx:alpine
spire/docker-compose.yaml         spire-server          ghcr.io/spiffe/spire-server:1.11.0
spire/docker-compose.yaml         spire-agent           ghcr.io/spiffe/spire-agent:1.11.0
mcp/Dockerfile                    (build target)        python:3.12-slim
```

---

## 6. Security Notes

- **Firewall (v2 baseline):** Default deny inbound. SSH restricted to `192.168.1.0/24`. Only port 9000 (A2A nginx) is effectively public.
- **SPIRE join token** (`6087b957-918f-4eed-a0da-813dcf887f10`) is stored in plaintext in `spire/agent/agent.conf`. This is the initial bootstrap token and should be rotated after first attestation.
- **insecure_bootstrap: true** in SPIRE agent — acceptable for initial setup; should be disabled after the trust bundle is established.
- **`.gitignore`** correctly excludes: `spire/data/`, `security/secrets/`, `*.key`, `*.pem`, `*.sock`, `*.sqlite3`, `shared_context/data/`, model blobs, Python caches.
- **PQC intent:** `agent-card.json` declares `ML-KEM-768` as the PQC standard — not yet implemented in code.
- **All containers** use `no-new-privileges: true` security option.
- **MCP Server** runs as non-root user `mcp_user` inside its container.
