# KITT Gateway — AI Context
> Last updated: 2026-03-17

## Project Identity

Sovereign AI gateway stack on KITT server. Multi-model fan-out engine (5 external + 1 local), SPIFFE/SPIRE zero-trust identity, Redis blackboard memory, Docker + systemd hybrid. Single operator, security-first.

Repo: `~/kitt_gateway`

## Repo Tree

```
kitt_gateway/
├── .claude/                  # Claude Code context + rules
│   ├── CLAUDE.md             # This file
│   ├── SYSTEM_BREAKDOWN.md   # Full technical reference
│   ├── TODO.md               # Open bugs + incomplete items
│   └── rules/                # Modular rule files (auto-loaded)
├── a2a/
│   ├── agent_zero/           # Core routing engine (systemd, :9001)
│   └── registry/             # Gateway capability manifest
├── a2a_proxy/                # A2A discovery proxy (nginx, :9000)
├── config/                   # Read-only config markers
├── docs/intelligence_archive/# Historical audit logs
├── governance/               # Kill switch + ATS telemetry
├── hub/                      # KITT Hub chat UI + router (systemd, :8080)
├── inference/                # Ollama edge inference (Docker, :11434)
├── mcp/                      # MCP context API (Docker, :8000)
├── orchestrator/             # LangGraph workflow router (standalone)
├── scripts/                  # Operational automation (sync, backup)
├── security/                 # Firewall baselines
├── shared_context/           # Redis blackboard (Docker, :6379)
├── spire/                    # SPIFFE/SPIRE identity layer
└── docker-compose.yml        # Root gateway sandbox
```

## Quick Commands

```bash
# Start stack (dependency order)
docker network create kitt_sovereign_net  # once only
cd spire          && docker compose up -d
cd shared_context && docker compose up -d
cd inference      && docker compose up -d
cd a2a_proxy      && docker compose up -d
docker compose up -d                      # root gateway
sudo systemctl start kitt-agent kitt-agent-http kitt-hub

# Status
sudo systemctl status kitt-agent kitt-agent-http kitt-hub
sudo journalctl -fu kitt-agent

# MCP
cd mcp && docker compose up -d

# Orchestrator
cd orchestrator && source .venv/bin/activate && python router.py
```

## Key References

- `.claude/SYSTEM_BREAKDOWN.md` — full architecture, data flows, port map, env vars
- `.claude/TODO.md` — open bugs, incomplete components, next priorities
- `docs/intelligence_archive/` — historical audit logs

## Close The Loop

When I type "close the loop": update this file's "Last updated" date + any changed sections, then give me the exact commands to update SYSTEM_BREAKDOWN.md if needed.

---

Every response should be secure by default and copy-paste ready for bash.
When in doubt, read the code first — never guess at what a service does.

## Rules

See `.claude/rules/` for modular rules on brand voice, content pillars, service offerings, and guardrails.

All files in `.claude/rules/` are automatically loaded at the same priority as this file and must be followed at all times.
