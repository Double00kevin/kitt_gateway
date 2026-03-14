# KITT Gateway — AI Context
> Last updated: 2026-03-13

## Project Identity
Sovereign AI gateway stack on KITT server. Multi-service (Docker + systemd daemons). Security-first, single operator.

Repo: `~/kitt_gateway`

## Canonical References
Full technical detail lives in these files — do not duplicate here:
- `.claude/SYSTEM_BREAKDOWN.md`
- `docs/intelligence_archive/` (historical only)

## Quick Commands
```bash
# Start stack (dependency order)
docker network create kitt_sovereign_net  # once only
cd spire         && docker compose up -d
cd shared_context && docker compose up -d
cd inference     && docker compose up -d
cd a2a_proxy     && docker compose up -d
docker compose up -d                     # root gateway
sudo systemctl start kitt-agent kitt-hub

# Status
sudo systemctl status kitt-agent kitt-hub
sudo journalctl -fu kitt-agent
sudo journalctl -fu kitt-hub

# MCP
cd mcp && docker compose up -d

# Orchestrator
cd orchestrator && source .venv/bin/activate && python router.py

Key Constraints

Four separate Python venvs — never mix: orchestrator/.venv, a2a/agent_zero/venv, hub/venv, mcp/venv
API keys only in a2a/agent_zero/.env (git-ignored)
Agent Zero + Hub run as systemd services, not Docker
Security-first on every command and config
ADHD: one step at a time unless “full plan” requested

Close The Loop
When I type "close the loop":

Update this file’s “Last updated” date + any changed sections
Give me the exact cat or echo commands to update .claude/SYSTEM_BREAKDOWN.md if needed