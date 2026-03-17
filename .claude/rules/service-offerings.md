## Core Gateway Services

### Agent Zero (a2a/agent_zero/)
- Core routing engine: `fan_out()` dispatches prompts to all model backends
- Runs as two systemd services: `kitt-agent` (daemon) + `kitt-agent-http` (:9001)
- API keys in `.env` (git-ignored) — never hardcode, never commit
- Health tick every 60s writes structured status to MCP `kitt_status` namespace

### KITT Hub (hub/)
- Chat UI + FastAPI router on :8080
- Calls Agent Zero over loopback HTTP (:9001) — no shared venv
- Returns 503 if Agent Zero is down; env toggle `USE_DIRECT_AGENT_ZERO=true` for rollback

### MCP Server (mcp/)
- FastAPI REST shim over Redis on :8000
- Fetches own X.509-SVID from SPIRE at startup (fail-open)
- Runs as non-root `mcp_user` in Docker with `no-new-privileges`

### Orchestrator (orchestrator/)
- LangGraph one-shot workflow router — standalone, not in Hub request path
- Own venv at `orchestrator/.venv` — never mix with other venvs

### Supporting Services
- **Redis** (`shared_context/`): blackboard state, loopback :6379
- **Ollama** (`inference/`): llama3.2 on NVIDIA GPU, loopback :11434
- **A2A Proxy** (`a2a_proxy/`): nginx agent discovery on :9000
- **SPIRE** (`spire/`): server :8081 + agent, host network mode
