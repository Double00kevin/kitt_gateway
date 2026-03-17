## Infrastructure Pillars

### Sovereignty
- All inference can fall back to Ollama + llama3.2 (air-gap capable)
- No external SaaS dependencies for core operation (Cloudflare, Vercel, etc. are banned)
- Single operator, single trust domain (`mpx.sovereign`)

### Zero-Trust Identity
- SPIFFE/SPIRE for all workload identity
- Every new service must have a registered SPIRE workload entry
- Trust domain: `mpx.sovereign` — never change without full re-attestation plan

### Blackboard Architecture
- Redis is the single shared state store — no side-channel state
- All agent context flows through MCP Server (`/context/store`, `/context/retrieve`)
- Max 5 entries per agent_id (capped via `ltrim`)

### Multi-Model Fan-Out
- Agent Zero dispatches to up to 6 backends in parallel (5 external + 1 local)
- Intent gate (llama3.2) pre-screens every prompt — flag-only, never blocks
- All flagged events logged to ATS audit log, MCP, and systemd journal
