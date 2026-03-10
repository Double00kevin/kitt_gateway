# CLAUDE.md

Guidance for Claude Code working in this repository.

## Canonical References

Full technical detail lives in these files — do not duplicate content here:

- **`PROJECT_CONTEXT.md`** — project identity, repo layout, how to use this context
- **`.claude/SYSTEM_BREAKDOWN.md`** — canonical architecture reference: directory structure, file purposes, env vars, data flows, port map
- **`docs/intelligence_archive/`** — historical audit logs only
- **`~/builder-os/01-projects/kitt_gateway/`** — STATUS.md, NEXT.md, LINKS.md (operator control plane)

## Quick Commands

**Start the stack** (bring up in dependency order):
```bash
docker network create kitt_sovereign_net          # once, if missing
cd spire         && docker compose up -d
cd shared_context && docker compose up -d
cd inference     && docker compose up -d
cd a2a_proxy     && docker compose up -d
docker compose up -d                              # gateway sandbox (repo root)
sudo systemctl start kitt-agent kitt-hub
```

**Check services:**
```bash
sudo systemctl status kitt-agent kitt-hub
sudo journalctl -fu kitt-agent    # Agent Zero logs
sudo journalctl -fu kitt-hub      # Hub logs (UI: http://localhost:8080)
```

**MCP Server** (port 8000, separate compose):
```bash
cd mcp && docker compose up -d && docker compose logs -f
```

**Orchestrator** (one-shot, LangGraph):
```bash
cd orchestrator && source .venv/bin/activate && python router.py
```

**Backup / sync:**
```bash
bash scripts/sync_kitt.sh
```

**Emergency stop:**
```bash
bash governance/kill_switch.sh   # stops inference + A2A proxy; Redis + SPIRE stay up
```

## Key Constraints

- Four separate Python venvs — do not mix: `orchestrator/.venv/`, `a2a/agent_zero/venv/`, `hub/venv/`, `mcp/venv/`
- API keys in `a2a/agent_zero/.env` (git-ignored); Hub inherits them via `sys.path` import
- Agent Zero and Hub are systemd daemons on the host, not Docker containers

# Builder-OS Control Plane
For current status and next actions, also read:
- ~/builder-os/01-projects/kitt_gateway/STATUS.md
- ~/builder-os/01-projects/kitt_gateway/NEXT.md
- Follow all rules in ~/builder-os/OPERATING_MODEL.md
