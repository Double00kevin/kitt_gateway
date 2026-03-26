# KITT Sovereign Gateway — Project Context
> Last updated: 2026-03-26 (33da6be)

KITT Sovereign Gateway is a sovereign AI agent security control plane for AI infrastructure. It provides multi-model fan-out dispatch with intent screening (llama3.2), SPIFFE/SPIRE zero-trust identity, a Redis blackboard for shared state, and a Hub UI with a live threat defense dashboard. Built for enterprise AI security consulting via MadProjX.

## The Business / Purpose

KITT Gateway secures AI agent infrastructure by screening every prompt through an intent gate (llama3.2), dispatching to multiple LLM backends in parallel, and logging all events to a structured Redis Streams audit trail. The Live Threat Defense Dashboard gives security teams real-time visibility into prompt injection, jailbreak attempts, data exfiltration, and other OWASP LLM Top 10 threats — with PDF report export for board-level reporting. Target audience is enterprise security teams and AI infrastructure operators evaluating sovereign AI controls.

## People

- **Kevin Hillis** — Owner/developer (CISSP, MadProjX AI consulting)

## Sub-Repos / Structure

| Directory | Purpose |
|-----------|---------|
| `a2a/` | Agent-to-Agent protocol — Agent Zero daemon + registry |
| `a2a_proxy/` | nginx proxy for A2A discovery (`/.well-known/agent-card.json`) |
| `config/` | Configuration files and kernel tripwire checks |
| `docs/` | Changelog, roadmap, architecture, intelligence archive |
| `events/` | Redis Streams event bus, threat detectors, dashboard aggregation, PDF reports, attack payloads |
| `governance/` | Kill switch (ISO 42001 cessation protocol) and audit logging |
| `hub/` | KITT Hub — FastAPI chat UI, multi-model fan-out, live dashboard |
| `inference/` | Docker Compose for Ollama (llama3.2 local LLM) |
| `mcp/` | MCP Server — FastAPI REST API over Redis blackboard |
| `orchestrator/` | LangGraph router with ATS telemetry logging |
| `security/` | Security baseline and policy docs |
| `shared/` | Shared modules (health checks, utilities) |
| `shared_context/` | Docker Compose for Redis (central blackboard) |
| `spire/` | SPIFFE/SPIRE identity infrastructure (server + agent containers) |
| `tests/` | pytest suite (83 tests across 6 files) |
| `scripts/` | Automation and utility scripts |

## Tech Ecosystem

- **Python 3 + FastAPI** — Hub (:8080), MCP Server (:8000), Agent Zero HTTP (:9001)
- **Redis 7.2** — Blackboard state store + Streams event bus
- **Ollama** — Local LLM inference (llama3.2 intent gate, :11434)
- **External LLMs** — Claude, GPT-4o, Gemini, Grok, Perplexity (parallel fan-out)
- **SPIFFE/SPIRE** — Zero-trust X.509-SVID identity (trust domain: `mpx.sovereign`)
- **Docker Compose** — Redis, Ollama, SPIRE, MCP Server orchestration
- **systemd** — Hub, Agent Zero, Agent Zero HTTP service management
- **nginx** — A2A proxy for agent discovery
- **pytest** — Test suite with Redis integration tests
- **slowapi** — Rate limiting (10 req/min on /chat)

## Architecture

```
Browser (:8080)
    |
KITT Hub (FastAPI, systemd)
    |-- Agent Zero HTTP (:9001)
    |       |-- Intent Gate (llama3.2 via Ollama :11434)
    |       |-- Fan-out (Claude, GPT-4o, Gemini, Grok, Perplexity)
    |       +-- MCP Server (:8000) <-> Redis (:6379)
    |
    |-- Events (Redis Streams -> Detectors -> Dashboard)
    |-- SPIRE Agent (Docker socket attestation)
    |       +-- SPIRE Server (:8081)
    +-- A2A Proxy (nginx :9000)
```

## Live Threat Defense Roadmap (Progressive Build)

| Stage | Scope | Status |
|-------|-------|--------|
| **Stage 1** | Threat dashboard — event aggregation, posture scoring (0-100), severity breakdown | Done |
| **Stage 2** | Redis Streams event bus — structured emit/read, TTL retention, request_id indexing | Done |
| **Stage 3** | Expanded detection + WebSocket — PII/exfiltration detectors, SSE demo mode, WS live stream | Done |
| **Stage 4** | Attack replay theater — 30+ OWASP-mapped payloads, replay endpoint, PDF report export | Done |

### Cherry-picks from CEO Review (2026-03-25)

- PDF security report export (board-ready posture assessment)
- Attack payload library (30+ OWASP LLM Top 10 mapped payloads)
- Comparative model response view (side-by-side multi-model output)
- Dedicated `/demo` endpoint (SSE-driven attack simulation)

## CSO Audit History

**2026-03-25 — 3 findings remediated:**
1. SPIRE tokens scrubbed from git history (BFG + force-push)
2. Bearer token auth added to Hub /chat and all API endpoints (KITT_HUB_API_KEY)
3. Rate limiting added (slowapi, 10 req/min per IP on /chat)

## TODOs

- **P2:** SIEM export — JSON webhook + syslog forwarding of Redis Streams events (~25 min)
- **P2:** SPIRE mTLS enforcement — mutual TLS between Agent Zero and MCP Server using SVIDs (~30 min)
- **P3:** Health check dedup — shared/health.py extracted, wire remaining consumers

## Conventions

- snake_case for Python modules, kebab-case for service/config files
- No secrets in repo — ever (env vars via .env, KITT_HUB_API_KEY for auth)
- Security-first: least privilege, validate inputs, fail-open on non-critical deps
- Every change gets a changelog entry in `docs/changelog.md`
- Tests live in `tests/` with `test_*.py` naming

## Obsidian Vault (Knowledge Base)

Kevin's personal knowledge base lives in an Obsidian vault ("AllTheThings") at `C:\Users\doubl\ObsidianVaults\AllTheThings`, synced via Google Drive to his phone. Project notes live in `Projects/Kitt/` inside the vault.

## GitHub

- **Repo:** Double00kevin/kitt_gateway
- **Branch:** master (primary)

## Close The Loop Protocol

When asked to "close the loop":
1. `git log -1 --oneline` to get latest commit.
2. Update "Last updated" date at top of this file.
3. Append summary to `docs/changelog.md` with commit hash.
4. Verify matching roadmap item is checked off.
5. Stage, commit (`docs: close the loop for [hash]`), and push.
