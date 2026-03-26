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
- **Blackboard memory:** Redis as the single shared state store (context + event bus)
- **Event-driven audit:** All security events flow through Redis Streams with structured emit/read
- **Defense in depth:** Intent gate (LLM) + regex detectors (PII, exfiltration, injection) + bearer token auth + rate limiting
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
├── docs/                    # Documentation (changelog, roadmap, architecture, intel archive)
├── events/                  # Live Threat Defense pipeline
│   ├── bus.py               # Redis Streams event bus (kitt:events stream)
│   ├── detectors.py         # Regex threat detectors (PII, exfiltration, injection)
│   ├── dashboard.py         # Event aggregation + posture scoring (0-100)
│   ├── payloads.py          # Attack payload library loader (OWASP LLM Top 10)
│   └── report.py            # PDF security report export
├── governance/
│   ├── kill_switch.sh       # Emergency stop script
│   └── telemetry/           # ATS audit log output
├── hub/                     # KITT Hub: chat UI + model router + dashboard
│   ├── main.py              # FastAPI app (:8080) — auth, rate limiting, all API routes
│   ├── kitt-hub.service     # systemd unit
│   ├── demo_payloads.json   # 30+ OWASP-mapped attack payloads
│   └── static/
│       └── dashboard.html   # Live Threat Defense Dashboard UI
├── inference/               # Ollama edge inference engine
├── mcp/                     # MCP Server (FastAPI context API over Redis)
│   ├── server.py            # REST shim with SPIRE SVID fetch at startup
│   ├── Dockerfile
│   └── docker-compose.yml
├── orchestrator/            # LangGraph workflow router (standalone)
│   └── router.py            # One-shot stateful graph execution
├── scripts/                 # Operational automation
├── security/                # Firewall baselines
├── shared/                  # Shared modules
│   └── health.py            # DRY health checks (MCP, Ollama, Redis)
├── shared_context/          # Redis blackboard
│   └── docker-compose.yaml
├── spire/                   # SPIFFE/SPIRE identity framework
│   ├── agent/               # SPIRE agent config
│   └── server/              # SPIRE server config
├── tests/                   # pytest suite (83 tests, 6 files)
│   ├── test_bus.py          # Event bus unit + integration tests
│   ├── test_detectors.py    # Detector patterns + edge cases
│   ├── test_dashboard.py    # Stats computation + posture score
│   ├── test_payloads.py     # Payload library loading + filtering
│   ├── test_report.py       # PDF generation + unicode handling
│   └── test_hub_routes.py   # All 11 Hub routes, auth, error cases
└── docker-compose.yml       # Root gateway sandbox definition
```

## Data Flows

### Primary Request Path

```
Browser  POST /api/chat {prompt, models}
    │    Authorization: Bearer <KITT_HUB_API_KEY>
    │
    └──▶ hub/main.py (:8080)
              │  [bearer token auth + rate limiting (10/min via slowapi)]
              │
              └──▶ POST http://127.0.0.1:9001/fan_out
                        │
                        ├──▶ check_intent() via llama3.2 (local pre-screen)
                        │         └──▶ emit("intent_gate", ...) → Redis Streams
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
                                  ├──▶ detectors.scan() → PII, exfiltration, injection checks
                                  │         └──▶ emit("detection", ...) → Redis Streams
                                  └──▶ return {model: response} to Hub → Browser
```

### Events Pipeline

```
Any component ──▶ events.bus.emit(layer, event_type, details, severity, request_id)
                        │
                        └──▶ Redis Streams (kitt:events, MAXLEN 10k)
                                  │
                                  ├──▶ GET /api/dashboard → events.dashboard.get_stats()
                                  │         └──▶ posture score (0-100), severity breakdown, layer stats
                                  │
                                  ├──▶ GET /api/demo (SSE) → fire attack payloads in sequence
                                  │         └──▶ events.payloads → 30+ OWASP LLM Top 10 mapped
                                  │
                                  ├──▶ POST /api/replay/{event_id} → replay single event
                                  │
                                  ├──▶ GET /api/report/pdf → events.report.generate_pdf()
                                  │         └──▶ board-ready posture assessment
                                  │
                                  └──▶ WS /ws/events → live WebSocket stream (token auth via query param)
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
- SSH restricted to LAN (<INTERNAL_SUBNET>/24)
- Internal services bound to 127.0.0.1
- Docker network `kitt_sovereign_net` isolates container traffic

### Container Hardening

- `no-new-privileges: true` on all containers
- MCP Server runs as non-root `mcp_user`
- Config files mounted read-only where possible
- SPIRE agent socket mounted read-only into workload containers

### Authentication & Rate Limiting

- Bearer token auth on all Hub API endpoints (`Authorization: Bearer <KITT_HUB_API_KEY>`)
- WebSocket auth via query parameter (`/ws/events?token=<token>`)
- Rate limiting on `/chat` — 10 requests/min per IP (slowapi)
- API key configured via `KITT_HUB_API_KEY` environment variable

### Intent Screening

- `check_intent()` pre-screens every prompt via llama3.2 before fan-out
- Categories: `none`, `prompt_injection`, `jailbreak`, `unsafe`
- Flag-only mode — never blocks, always logs
- All intent events emitted to Redis Streams (`kitt:events`)
- Hub returns `intent_flagged`, `intent_category`, `intent_score` in every response

### Threat Detection Pipeline

- Regex-based detectors run on every request after fan-out (`events/detectors.py`)
- PII detection: SSN, email, phone, credit card patterns
- Data exfiltration: base64 blocks, URL encoding, "send to" patterns
- Indirect prompt injection: ignore_previous, system_prefix, role_override
- All findings emitted to Redis Streams with type, subtype, confidence, and severity
- Detectors run as a separate pipeline stage from the intent gate

### Governance

- Kill switch halts inference and external communication
- Redis and SPIRE remain running (preserves state and identity)
- Append-only Redis Streams audit trail for all security events (10k max, TTL-trimmed)
- ISO 42001 alignment for AI system governance
