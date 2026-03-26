# Roadmap

Current status and planned work for KITT Sovereign Gateway.

## Completed

| ID | Description | Date |
|----|-------------|------|
| B1 | Fixed hardcoded Docker bridge IPs — switched to Docker DNS names | 2026-02-28 |
| B2 | Kill switch now stops Hub and Agent Zero (systemd) | 2026-02-28 |
| B3 | Fan-out parallelized via ThreadPoolExecutor (was sequential ~150s) | 2026-02-28 |
| B4 | Orchestrator writes actual LLM response to Redis (was hardcoded string) | 2026-03-01 |
| B5 | SPIFFE trust domain unified to `mpx.sovereign` across all agent cards | 2026-03-01 |
| B6 | Removed stale ledger.json (nothing read/wrote to it) | 2026-03-13 |
| I1 | SPIRE workload attestation wired — MCP Server fetches SVID at startup | 2026-03-14 |
| I2 | Intent gate implemented — llama3.2 pre-screens all prompts | 2026-03-13 |
| I5 | Agent Zero daemon loop connected to health monitoring | 2026-03-01 |
| I6 | Hub /health endpoint validates MCP and Ollama connectivity | 2026-03-01 |
| S1 | Hub bearer token auth + rate limiting on /chat | 2026-03-19 |
| D1 | Live Threat Defense Dashboard — event bus, detectors, replay, demo mode | 2026-03-26 |
| D2 | Attack payload library — 30+ OWASP LLM Top 10 mapped payloads | 2026-03-26 |
| D3 | PDF security report export — board-ready posture assessment | 2026-03-26 |
| D4 | Shared health module — DRY extraction from Hub, Agent, Dashboard | 2026-03-26 |
| T1 | Comprehensive test suite — 83 tests across 6 test files | 2026-03-26 |
| I7 | SPIRE bootstrap hardened — insecure_bootstrap=false, bundle pinned | 2026-03-13 |
| A1 | Hub decoupled from Agent Zero — HTTP service on loopback :9001 | 2026-03-13 |
| M1-M4 | Missing repo files committed (service units, .env.example, pinned deps, docs) | 2026-02-28 to 2026-03-01 |

## In Progress

### A2 — Agent card endpoints reference localhost

Agent Zero's agent-card.json lists `localhost` URLs for capability endpoints. These need to be LAN-resolvable for cross-network agent discovery to work.

### I4 — Edge router capabilities not yet implemented

The public agent card advertises `pii_masking`, `intent_classification`, and `local_routing` as capabilities. These are planned but not yet functional. The local llama3.2 model is available and could power these features.

### I3 — Post-quantum cryptography declared but not implemented

`agent-card.json` declares `ML-KEM-768` as the PQC standard. No post-quantum crypto is present in the stack yet. All external API calls use standard TLS. SPIRE uses RSA-2048 for the CA key. This is forward-looking — implementation depends on upstream library support.

## Planned

### SVID-based request authorization

Currently the MCP Server fetches its own SVID at startup but doesn't enforce SVID verification on incoming requests. Next step: mutual TLS between Agent Zero and MCP Server using SPIRE-issued SVIDs.

### Multi-agent orchestration

The current architecture supports a single Agent Zero instance. Planned: registration and discovery of multiple specialized agents, each with their own SPIRE identity and capability declarations.

### Policy engine

Governance currently consists of the kill switch and audit logging. Planned: declarative policy rules (YAML) for controlling which agents can communicate, which models they can access, and what data can flow between them.

### ~~Expanded intent categories~~ → Completed (2026-03-26)

PII detection, data exfiltration patterns, and indirect injection detection implemented in `events/detectors.py`. Regex-first approach for predictable latency. Intent gate retains the original 4 categories; new detectors run as a separate pipeline stage.

### Edge capabilities

PII masking, local routing decisions, and intent classification at the gateway edge — all running on the local llama3.2 model before any data leaves the network.
