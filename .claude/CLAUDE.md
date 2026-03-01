# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Identity

KITT Sovereign Gateway — a sovereign AI infrastructure that fans out prompts to multiple AI backends simultaneously. Local inference runs via Ollama (llama3.2 on NVIDIA GPU); external inference routes to Anthropic Claude, OpenAI ChatGPT, Google Gemini, xAI Grok, and Perplexity. Identity is cryptographically enforced via SPIFFE/SPIRE. The trust domain is `mpx.sovereign`.

## Running the Stack

Each subsystem has its own `docker-compose.yaml`. They are **not** orchestrated by a single top-level compose file. Bring them up in dependency order:

```bash
# 1. Pre-requisite: create the shared Docker network (once)
docker network create kitt_sovereign_net

# 2. Identity layer (must be first)
cd spire && docker compose up -d

# 3. Shared memory (Redis blackboard)
cd shared_context && docker compose up -d

# 4. Inference engine (Ollama + GPU)
cd inference && docker compose up -d

# 5. A2A discovery proxy (nginx)
cd a2a_proxy && docker compose up -d

# 6. Gateway sandbox (main container)
docker compose up -d   # from repo root

# 7. Agent Zero (systemd daemon, not Docker)
sudo systemctl start kitt-agent
sudo systemctl status kitt-agent
sudo journalctl -fu kitt-agent   # follow logs

# 8. KITT Hub (systemd daemon, not Docker)
sudo systemctl start kitt-hub
sudo systemctl status kitt-hub
sudo journalctl -fu kitt-hub     # follow logs
# UI available at http://localhost:8080
```

## Running Individual Components

**MCP Server** (FastAPI context API, port 8000):
```bash
cd mcp
docker compose up -d   # uses mcp/docker-compose.yml; builds from Dockerfile on first run
docker compose logs -f
```

**Orchestrator** (LangGraph router, one-shot execution):
```bash
cd orchestrator
source .venv/bin/activate
python router.py
```

**Agent Zero** (daemon, managed via systemd):
```bash
cd a2a/agent_zero
source venv/bin/activate
python agent.py   # runs daemon loop; Ctrl-C to stop
```

**KITT Hub** (chat UI + model router, port 8080):
```bash
cd hub
source venv/bin/activate
python main.py    # or: uvicorn main:app --host 0.0.0.0 --port 8080
```

## Backup & Sync

```bash
bash scripts/sync_kitt.sh   # commits all changes and pushes to ssd-vault + origin
```

## Emergency Stop (Governance)

```bash
bash governance/kill_switch.sh   # stops inference + A2A proxy; Redis and SPIRE stay up
```

## Architecture: How the Pieces Connect

The system uses a **blackboard pattern** — all components share state through Redis (`127.0.0.1:6379`). There is no direct RPC between agents; they read and write named keys.

**Primary request flow (Hub → Agent Zero → APIs):**
1. Browser sends `POST /chat {prompt, models}` to `hub/main.py` (port 8080)
2. Hub calls `AgentZero.fan_out(prompt, models)` — Agent Zero is imported directly via `sys.path` insertion pointing at `a2a/agent_zero/`
3. `fan_out()` fetches conversation history from MCP Server (`GET /context/retrieve`), then dispatches to each requested model in sequence
4. Each model call is a direct HTTPS request to its API using keys from `a2a/agent_zero/.env`
5. Each response is stored back to MCP Server (`POST /context/store`) and returned to the Hub as `{model: response}` dict
6. Hub returns the full dict to the browser; the UI renders one response card per model

**Available models in `fan_out()`:**
- `"claude"` → `claude-sonnet-4-20250514` (Anthropic API)
- `"openai"` → `gpt-4o` (OpenAI API)
- `"gemini"` → `gemini-2.5-flash` (Google Generative Language API)
- `"grok"` → `grok-3-latest` (xAI API)
- `"perplexity"` → `sonar-pro` (Perplexity API)
- `"local"` → `llama3.2:latest` via Ollama (`:11434`) — pulled and working

Default fan_out (when `models=None`) sends to all five external APIs; `"local"` must be explicitly selected.

**MCP memory flow:**
- `mcp/server.py` is a REST shim over Redis — `POST /context/store` and `GET /context/retrieve`
- Keys: `agent:<agent_id>:context` (Redis list, capped at 5 entries)
- MCP container (`mpx-mcp-server`) connects to Redis at `172.20.0.2` (set via `REDIS_HOST` env var in `mcp/docker-compose.yml`); Agent Zero reaches MCP at `172.18.0.2:8000` (hardcoded in `agent.py`)
- History is serialized as JSON strings `{"role": "user"|"assistant", "content": "..."}` and deserialized by `_history_to_messages()` before being sent to external APIs (last 6 entries, Gemini uses last 4)

**Orchestrator (standalone):**
- `orchestrator/router.py` is a separate one-shot LangGraph workflow. It reads/writes `"mission_status"` in Redis directly (not via MCP Server) and logs to `governance/telemetry/ats_audit.log`. It is independent of the Hub/Agent Zero request path.

**Identity flow:** SPIRE Server (`:8081`) attests the SPIRE Agent via join token → Agent exposes the workload API socket at `spire/sockets/agent.sock` → this socket is bind-mounted read-only into `kitt_sandbox` at `/run/spire/sockets`. The MCP Server has the socket path wired in (`SPIRE_SOCKET`) but workload attestation is not yet called — it's reserved for future use.

**A2A Discovery:** `mpx-a2a-proxy` (nginx, `:9000`) serves `a2a_proxy/html/.well-known/agent-card.json`. Port 8080 (Hub) is also public-facing.

**Agent registry:** `a2a/registry/gateway-manifest.json` is the authoritative list of active agents. `a2a/agent_zero/agent-card.json` is Agent Zero's identity card (referenced by the registry). Both are static JSON — update them manually when agents are added or change version.

## Key Hardcoded Values to Know

- Redis key for orchestrator state: `"mission_status"`
- Redis key pattern for MCP context: `"agent:<agent_id>:context"`
- MCP_URL in `agent.py`: `http://localhost:8000` (Agent Zero is a host process; MCP port is bound to `127.0.0.1:8000` on the host)
- REDIS_HOST in `mcp/docker-compose.yml`: `mpx-shared-context` (Docker DNS name; Redis is on `kitt_sovereign_net`)
- Hub imports Agent Zero directly: `sys.path.insert(0, '../a2a/agent_zero')` then `from agent import AgentZero` — the two components are tightly coupled by filesystem path
- SPIFFE IDs in use: `spiffe://mpx.sovereign/kitt_node/edge_router` (edge router), `spiffe://kitt.local/agent_zero` (Agent Zero)
- SPIRE join token is in plaintext at `spire/agent/agent.conf` — rotate after first attestation
- `insecure_bootstrap: true` in `spire/agent/agent.conf` is intentional for initial setup; disable after trust bundle is established

## What Is and Isn't Containerized

| Component | Runtime |
|-----------|---------|
| Redis | Docker (`mpx-shared-context`) |
| Ollama / llama3.2 | Docker (`mpx-inference-edge`) |
| A2A Proxy | Docker (`mpx-a2a-proxy`) |
| SPIRE Server + Agent | Docker (`spire-server`, `spire-agent`) |
| Gateway Sandbox | Docker (`kitt_sandbox`) |
| MCP Server | Docker (`mpx-mcp-server`, via `mcp/docker-compose.yml`) |
| Agent Zero daemon | systemd on host (`kitt-agent.service`) |
| KITT Hub | systemd on host (`kitt-hub.service`) |
| Orchestrator / router | Python venv on host (`.venv` in `orchestrator/`) |

## Python Environments

There are **three separate Python virtual environments** — do not mix them:
- `orchestrator/.venv/` — LangChain, LangGraph, langchain-ollama, redis, numpy (Python 3.12)
- `a2a/agent_zero/venv/` — requests, python-dotenv, certifi (Python 3.12)
- `hub/venv/` — fastapi, uvicorn, python-dotenv, requests (Python 3.12)

`hub/main.py` imports `AgentZero` directly from `a2a/agent_zero/agent.py` via `sys.path` injection. The Hub's venv must satisfy Agent Zero's imports (`requests`, `python-dotenv`) as well as its own.

To install the Hub service on a new host:
```bash
sudo cp hub/kitt-hub.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable kitt-hub
```

## Git & Secrets

`.gitignore` excludes: `spire/data/`, `spire/socket/`, `security/secrets/`, `shared_context/data/`, `*.key`, `*.pem`, `*.sock`, `*.sqlite3`, model blobs (`*.gguf`, `models/`), `.env`, and all Python caches.

API keys live in `a2a/agent_zero/.env` (git-ignored). Required keys:
```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
GROK_API_KEY=
PERPLEXITY_API_KEY=
```
The Hub inherits these automatically because it imports `agent.py`, which calls `load_dotenv()` on that file at import time.
