# TODOS

## P2: SIEM Export (syslog/JSON webhook)
**What:** Forward Redis Streams events to external SIEM systems via syslog or JSON webhook.
**Why:** Enterprise consulting prospects will ask "does it integrate with Splunk/QRadar?" — this is question #2 after the demo.
**Pros:** Completes the enterprise integration story. Event bus (Stage 2) makes this straightforward — it's just a consumer on the same Redis Stream.
**Cons:** Adds external connectivity that complicates the sovereignty narrative. Needs endpoint config, format selection, and outbound auth.
**Context:** The events/bus.py Redis Streams infrastructure is the foundation. A SIEM exporter would be a new consumer that reads from `kitt:events` and forwards to a configurable endpoint. Start with JSON webhook, add syslog later.
**Effort:** M (human: ~1 week) → with CC: S (~25 min)
**Depends on:** Stage 2 event bus (events/bus.py) — already implemented.

## P2: SPIRE mTLS Enforcement
**What:** Enable mutual TLS between Agent Zero and MCP Server using SPIRE-issued SVIDs.
**Why:** SPIRE identity is currently fetch-and-log only. A CISO will ask "is this enforced?" and the honest answer is "not yet." Completing mTLS makes the zero-trust story real.
**Pros:** Elevates SPIRE from decorative to functional. Enables SVID-based access control on MCP endpoints.
**Cons:** Requires py-spiffe mTLS configuration in both services. Docker socket access patterns may need adjustment. May require SPIRE registration entry updates.
**Context:** MCP Server already fetches its SVID at startup (`mcp/server.py` lifespan). Agent Zero needs its own SVID fetch + requests library configured with client cert. The SPIRE agent socket is already mounted into containers.
**Effort:** M (human: ~1 week) → with CC: S (~30 min)
**Depends on:** Nothing — can be done independently.

