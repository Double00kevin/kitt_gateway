# KITT Sovereign Gateway

A local-first, sovereign AI infrastructure gateway that unifies identity, governance, and security into a single control plane for AI agent workloads.

```
┌─────────────────────────────────────────────────────────────────┐
│                     KITT Sovereign Gateway                       │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│  │  A2A     │  │   MCP    │  │ Inference │  │  Governance  │  │
│  │  Proxy   │  │  Context │  │  Router   │  │  + Kill SW   │  │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └──────┬───────┘  │
│       │              │              │               │           │
│       └──────────────┴──────┬───────┴───────────────┘           │
│                             │                                   │
│                    ┌────────┴────────┐                          │
│                    │  SPIFFE/SPIRE   │                          │
│                    │  Identity Layer │                          │
│                    │  mpx.sovereign  │                          │
│                    └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## What This Is

KITT Gateway is an integrated security control plane for AI agent infrastructure. It sits between your agents and the outside world — enforcing identity, screening threats, routing inference, and managing context through a single trust domain.

Most AI agent frameworks (OpenClaw, LangGraph, CrewAI) focus on what agents *do*. KITT Gateway focuses on the infrastructure *between* agents — the part that handles identity, communication security, and governance.

## What It Does

**Multi-model fan-out** — Dispatches prompts to up to 6 backends simultaneously (Claude, GPT-4o, Gemini, Grok, Perplexity, and local Ollama). Compare responses side-by-side from a single chat interface.

**SPIFFE/SPIRE identity** — Every workload gets a cryptographic identity (X.509-SVID) issued by SPIRE under the `mpx.sovereign` trust domain. The MCP Server fetches its own SVID at startup and attests via Docker workload selectors.

**A2A agent discovery** — Agent cards published at `/.well-known/agent-card.json` via an nginx proxy. Declares capabilities, SPIFFE IDs, and security requirements per the A2A protocol.

**MCP context management** — A FastAPI REST API over Redis that stores and retrieves agent context. All shared state flows through this single blackboard — no side-channel state.

**Intent-based threat screening** — Every prompt is pre-screened by a local LLM (llama3.2) before fan-out. Flags prompt injection, jailbreak attempts, and unsafe content. Flag-only (never blocks) with full audit trail.

**Live Threat Defense Dashboard** — Real-time security visibility with event aggregation, severity breakdown, and a security posture score (0-100). WebSocket live streaming for continuous monitoring, SSE-driven demo mode for live attack simulations, and attack replay theater for forensic walkthroughs.

**Attack payload library** — 30+ pre-built attack payloads mapped to the OWASP LLM Top 10 (prompt injection, jailbreak, data exfiltration, role confusion, and more). Used for demo mode, red team training, and detection validation.

**PDF security report export** — Board-ready posture assessment with attack replay timeline, severity breakdown, and posture scoring. One-click export from the dashboard for leave-behind artifacts.

**Threat detection pipeline** — Regex-based detectors for PII (SSN, email, phone, credit card), data exfiltration patterns (base64, URL encoding), and indirect prompt injection. Runs as a separate pipeline stage after the intent gate, with all findings logged to the Redis Streams audit trail.

**Governance and kill switch** — ISO 42001-aligned emergency cessation. One script stops all inference and communication while preserving memory and identity state.

**Air-gap capable** — Core operation requires zero external dependencies. All inference can fall back to Ollama + llama3.2 running on a local GPU.

## Architecture

```
Browser → KITT Hub (:8080) ─→ Bearer token auth + rate limiting
              │
              ├→ Agent Zero HTTP (:9001) ─→ fan_out()
              │        │
              │        ├→ check_intent() ─→ Ollama/llama3.2 (local screening)
              │        │
              │        ├→ MCP Server (:8000) ─→ Redis blackboard (:6379)
              │        │
              │        ├→ Claude, GPT-4o, Gemini, Grok, Perplexity (external)
              │        └→ Ollama (:11434) (local inference)
              │
              └→ Events pipeline
                       ├→ Redis Streams (kitt:events) ─→ structured audit trail
                       ├→ Threat detectors ─→ PII, exfiltration, injection
                       ├→ Dashboard aggregation ─→ posture score (0-100)
                       ├→ WebSocket (/ws/events) ─→ live event stream
                       └→ PDF report export ─→ board-ready artifact

Identity: SPIRE Server (:8081) → SPIRE Agent → workload SVIDs
A2A:      nginx proxy (:9000) → /.well-known/agent-card.json
```

| Service | Port | Bind | Exposure |
|---------|------|------|----------|
| Redis (blackboard) | 6379 | 127.0.0.1 | Loopback only |
| MCP Server | 8000 | 127.0.0.1 | Loopback only |
| KITT Hub (chat UI) | 8080 | 0.0.0.0 | LAN |
| SPIRE Server | 8081 | host network | Host |
| A2A Proxy (nginx) | 9000 | 0.0.0.0 | Public |
| Agent Zero HTTP | 9001 | 127.0.0.1 | Loopback only |
| Ollama inference | 11434 | 127.0.0.1 | Loopback only |

All internal services bind to loopback. Only the Hub (LAN) and A2A proxy (public discovery) are network-accessible.

## Project Status

**Working today:**
- Multi-model fan-out with parallel dispatch (ThreadPoolExecutor)
- SPIRE identity layer with hardened bootstrap (no insecure_bootstrap)
- MCP Server with SVID fetch at startup (fail-open)
- Intent gate screening all prompts via local llama3.2
- Agent Zero running as decoupled HTTP service (systemd-managed)
- Hub chat UI with intent metadata in responses
- Bearer token auth (KITT_HUB_API_KEY) on all Hub API endpoints
- Rate limiting (10 req/min per IP on /chat via slowapi)
- Live Threat Defense Dashboard with real-time event feed
- Redis Streams event bus (kitt:events) with structured emit/read
- Threat detectors: PII, data exfiltration, indirect prompt injection
- Security posture scoring (0-100) with severity breakdown
- Attack payload library (30+ OWASP LLM Top 10 mapped)
- SSE demo mode (/api/demo) for live attack simulations
- Attack replay theater (/api/replay) for forensic walkthroughs
- PDF security report export (/api/report/pdf)
- WebSocket live event streaming (/ws/events)
- Comparative model response view (side-by-side multi-model output)
- Kill switch stopping inference + comms while preserving state
- 83 tests across 6 test files (pytest)
- 3-2-1 automated backup (local SSD + GitHub)

**In progress:**
- A2A agent-card endpoints reference localhost (need LAN-resolvable addresses)
- Edge router capabilities (PII masking, local routing) declared but not implemented
- Post-quantum crypto (ML-KEM-768) declared in agent cards, not yet in stack

**Planned:**
- SIEM export (JSON webhook + syslog forwarding)
- SPIRE mTLS enforcement between Agent Zero and MCP Server

See [docs/roadmap.md](docs/roadmap.md) for the full status breakdown.

## Requirements

- Linux host (developed on Ubuntu 24.04 LTS)
- Docker + Docker Compose
- NVIDIA GPU (for Ollama local inference)
- Python 3.12+
- At least one external API key (Anthropic, OpenAI, Google, xAI, or Perplexity) — or run fully local with Ollama only

## Quick Start

```bash
# 1. Create the Docker network
docker network create kitt_sovereign_net

# 2. Start core services
cd shared_context && docker compose up -d    # Redis
cd ../inference && docker compose up -d       # Ollama
cd ../mcp && docker compose up -d             # MCP Server
cd ../spire && docker compose up -d           # SPIRE Server + Agent

# 3. Pull a local model
docker exec mpx-inference-edge ollama pull llama3.2

# 4. Configure API keys
cp a2a/agent_zero/.env.example a2a/agent_zero/.env
# Edit .env with your API keys

# 5. Install and start systemd services
sudo cp hub/kitt-hub.service /etc/systemd/system/
sudo cp a2a/agent_zero/kitt-agent.service /etc/systemd/system/
sudo cp a2a/agent_zero/kitt-agent-http.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kitt-hub kitt-agent kitt-agent-http

# 6. Open the Hub
# Browse to http://<your-host-ip>:8080
```

## Security Design

- **Zero-trust identity:** SPIFFE SVIDs per workload, trust domain `mpx.sovereign`
- **Hardened SPIRE bootstrap:** `insecure_bootstrap = false`, server trust bundle pinned
- **Container hardening:** `no-new-privileges: true`, non-root users, read-only config mounts
- **Network isolation:** Internal services on loopback only, external surface minimized
- **Intent screening:** Local LLM pre-screens every prompt before external dispatch
- **Bearer token auth:** HMAC-based API key on all Hub endpoints, WebSocket auth via query param
- **Rate limiting:** 10 req/min per IP on /chat (slowapi)
- **Audit trail:** All events logged to append-only Redis Streams with TTL retention
- **Threat detection:** Regex-based PII, exfiltration, and injection detectors on every request
- **Emergency cessation:** Kill switch halts inference and comms, preserves identity and memory
- **Default deny firewall:** UFW baseline with SSH restricted to LAN

## Why This Exists

The AI agent ecosystem has a gap. Frameworks like OpenClaw, LangGraph, and CrewAI handle what agents do. Infrastructure tools like NVIDIA NemoClaw, Solo.io's agentgateway, and NVIDIA's Agent Toolkit handle pieces of the security puzzle. But getting identity, governance, inference routing, and protocol security requires assembling 4-5 separate products.

KITT Gateway is one person's attempt to build the integrated layer that connects these emerging standards — a single enforcement point where SPIFFE identity, A2A communication, MCP context, inference routing, and governance policy all converge.

The IETF draft for AI agent authentication is version -00. The industry is figuring this out in real time. This project is a working prototype of what that integrated security control plane could look like.

## License

[Apache License 2.0](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. This project is in early development — issues and feedback are welcome, pull requests by discussion.
