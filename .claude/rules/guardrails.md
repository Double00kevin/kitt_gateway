## Guardrails

These guardrails apply to every task in this repository.

### Venvs
- Four separate Python venvs — NEVER mix: `orchestrator/.venv`, `a2a/agent_zero/venv`, `hub/venv`, `mcp/venv`
- Never install packages into the wrong venv
- Never use pip at the system level

### Secrets
- API keys ONLY in `a2a/agent_zero/.env` (git-ignored)
- Never hardcode keys, tokens, or credentials in source files
- Never commit `.env`, `*.key`, `*.pem`, or `*.sock` files

### Docker & Services
- Agent Zero + Hub run as systemd services, NOT Docker containers
- All containers must use `no-new-privileges: true`
- Docker network `kitt_sovereign_net` is pre-created and external — never recreate in compose files
- Loopback-only binds for internal services (Redis, Ollama, MCP, Agent Zero)

### Git & Backup
- Two remotes: `origin` (GitHub) + `ssd-vault` (local SSD)
- `scripts/sync_kitt.sh` handles 3-2-1 backup — use it, don't roll your own
- Never force-push without explicit operator approval

### Banned
- Never suggest Yarn, Bun, Netlify, Vercel, Prisma, or Supabase
- Never use `sys.path` injection to import across service boundaries
- Never bypass SPIRE identity — all new workloads get registered entries
