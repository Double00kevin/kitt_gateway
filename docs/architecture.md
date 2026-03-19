# Architecture

Detailed technical architecture for KITT Sovereign Gateway.

## High-Level Overview

KITT Gateway is a **local-first, sovereign AI infrastructure** that fans out prompts to multiple AI backends simultaneously. Local inference runs via Ollama (llama3.2 on NVIDIA GPU); external inference routes to Anthropic Claude, OpenAI GPT-4o, Google Gemini, xAI Grok, and Perplexity. The design follows a blackboard pattern — all components share state through Redis — and cryptographic identity is enforced via SPIFFE/SPIRE.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          HOST MACHINE (Linux)                           │
│                                                                         │
│  [systemd: kitt-hub.service :8080]   [systemd: kitt-agent.service]      │
│        │                           [systemd: kitt-agent-http.service]   │
│        ▼                                     ▼                          │
│  ┌──────────────┐  POST /fan_out  ┌──────────────────┐                  │
│  │   KITT Hub   │────HTTP:9001───▶│   Agent Zero     │                  │
│  │  FastAPI     │   (loopback)    │  FastAPI :9001   │                  │
│  │  :8080       │                 │  + daemon mode   │                  │
│  └──────────────┘                 └────────┬─────────┘                  │
│                                            │                            │
│  External APIs (via Agent Zero):           ▼                            │
│  ┌─────────────────────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Claude · GPT-4o · Gemini   │  │  MCP Server  │  │  Redis (SCS)  │  │
│  │ Grok · Perplexity · Local  │  │  FastAPI     │──▶│  Blackboard   │  │
│  └─────────────────────────────┘  │  :8000       │  │  :6379        │  │
│                                   └──────────────┘  └───────────────┘  │
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

## Design Principles

- **Multi-model fan-out:** Simultaneous dispatch to up to 6 backends (5 external + 1 local)
- **Sovereign/air-gap capable:** All inference can fall back to Ollama + llama3.2
- **Zero-trust identity:** SPIFFE SVIDs issued per workload by SPIRE
- **Blackboard memory:** Redis as the single shared state store
- **Hardened containers:** `no-new-privileges`, non-root users, read-only config mounts
- **Governance:** ISO 42001-aligned kill switch for immediate cessation

## Directory Structure

```
kitt_gateway/
├── a2a/
│   ├── agent_zero/          # Agent Zero: routing engine, daemon, HTTP service
│   │   ├── agent.py         # Core fan_out() engine + FastAPI HTTP service (:9001)
│   │   ├── agent-card.json  # A2A identity descriptor
│   │   ├── kitt-agent.service        # systemd unit — daemon mode
│   │   └── kitt-agent-http.service   # systemd unit — HTTP service (:9001)
│   └── registry/            # Gateway capability manifest
├── a2a_proxy/               # A2A discovery proxy (nginx)
│   └── html/.well-known/    # Public agent-card endpoint
├── config/                  # Read-only kernel/config markers
├── docs/                    # Documentation
├── governance/
│   ├── kill_switch.sh       # Emergency stop script
│   └── telemetry/           # ATS audit log output
├── hub/                     # KITT Hub: chat UI + model router
│   ├── main.py              # FastAPI app (:8080)
│   ├── kitt-hub.service     # systemd unit
│   └── static/              # Frontend assets
├── inference/               # Ollama edge inference engine
├── mcp/                     # MCP Server (FastAPI context API over Redis)
│   ├── server.py            # REST shim with SPIRE SVID fetch at startup
│   ├── Dockerfile
│   └── docker-compose.yml
├── orchestrator/            # LangGraph workflow router (standalone)
│   └── router.py            # One-shot stateful graph execution
├── scripts/                 # Operational automation
├── security/                # Firewall baselines
├── shared_context/          # Redis blackboard
│   └── docker-compose.yaml
├── spire/                   # SPIFFE/SPIRE identity framework
│   ├── agent/               # SPIRE agent config
│   └── server/              # SPIRE server config
└── docker-compose.yml       # Root gateway sandbox definition
```

## Data Flows

### Primary Request Path

```
Browser  POST /chat {prompt, models}
    │
    └──▶ hub/main.py (:8080)
              │
              └──▶ POST http://127.0.0.1:9001/fan_out
                        │
                        ├──▶ check_intent() via llama3.2 (local pre-screen)
                        ├──▶ retrieve_context() from MCP
                        ├──▶ store_context(prompt) to MCP
                        │
                        ├──▶ call_claude()     ──▶ Anthropic API
                        ├──▶ call_openai()     ──▶ OpenAI API
                        ├──▶ call_gemini()     ──▶ Google API
                        ├──▶ call_grok()       ──▶ xAI API
                        ├──▶ call_perplexity() ──▶ Perplexity API
                        └──▶ call_local()      ──▶ Ollama (:11434)
                                  │
                                  └──▶ return {model: response} to Hub → Browser
```

### Health Monitoring (every 60s)

```
kitt-agent.service → agent.py::run_daemon()
    ├──▶ uptime, docker ps
    ├──▶ GET MCP /health
    ├──▶ GET Ollama /api/tags
    └──▶ POST MCP /context/store (agent_id="kitt_status")
```

### Emergency Kill Switch

```
$ bash governance/kill_switch.sh
    ├──▶ docker stop mpx-inference-edge   (Ollama)
    ├──▶ docker stop mpx-a2a-proxy        (nginx)
    ├──▶ systemctl stop kitt-hub           (chat UI)
    └──▶ systemctl stop kitt-agent         (Agent Zero)
    [Redis + SPIRE remain running — memory and identity preserved]
```

## Service Map

| Service | Container/Unit | Image/Runtime | Port | Status |
|---------|---------------|---------------|------|--------|
| Redis (blackboard) | mpx-shared-context | redis:alpine | 127.0.0.1:6379 | Running |
| Ollama (inference) | mpx-inference-edge | ollama/ollama:latest | 127.0.0.1:11434 | Running |
| MCP Server | mpx-mcp-server | python:3.12-slim | 127.0.0.1:8000 | Running |
| A2A Proxy | mpx-a2a-proxy | nginx:alpine | 0.0.0.0:9000 | Available |
| SPIRE Server | spire-server | spire-server:1.11.0 | host:8081 | Running |
| SPIRE Agent | spire-agent | spire-agent:1.11.0 | host network | Running |
| KITT Hub | kitt-hub.service | Python/systemd | 0.0.0.0:8080 | Running |
| Agent Zero (daemon) | kitt-agent.service | Python/systemd | — | Running |
| Agent Zero (HTTP) | kitt-agent-http.service | Python/systemd | 127.0.0.1:9001 | Running |

## Security Architecture

### Identity (SPIFFE/SPIRE)

- Trust domain: `mpx.sovereign`
- SPIRE Server issues X.509-SVIDs to registered workloads
- MCP Server fetches its SVID at startup via py-spiffe WorkloadApiClient
- SPIRE Agent uses Docker workload attestation (docker.sock mounted read-only)
- Bootstrap hardened: `insecure_bootstrap = false`, trust bundle pinned
- CA key type: RSA-2048

### Network

- Default deny firewall (UFW)
- SSH restricted to LAN (192.168.1.0/24)
- Internal services bound to 127.0.0.1
- Docker network `kitt_sovereign_net` isolates container traffic

### Container Hardening

- `no-new-privileges: true` on all containers
- MCP Server runs as non-root `mcp_user`
- Config files mounted read-only where possible
- SPIRE agent socket mounted read-only into workload containers

### Intent Screening

- `check_intent()` pre-screens every prompt via llama3.2 before fan-out
- Categories: `none`, `prompt_injection`, `jailbreak`, `unsafe`
- Flag-only mode — never blocks, always logs
- Flagged events logged to ATS audit log (prompt hash only, not plaintext)
- Hub returns `intent_flagged`, `intent_category`, `intent_score` in every response

### Governance

- Kill switch halts inference and external communication
- Redis and SPIRE remain running (preserves state and identity)
- Append-only ATS audit log for all orchestrator events
- ISO 42001 alignment for AI system governance
