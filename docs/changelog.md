# Changelog

## 2026-03-19

- `155cc6e` — **security: scrub secrets, usernames, and internal IPs from tracked files**
  - Redacted SPIRE join token (`fc0aa621-…`) with `<SPIRE_JOIN_TOKEN>` placeholder
  - Removed `spire/bootstrap.crt` and `spire/agent/bootstrap.crt` from tracking
  - Added `*.crt` to `.gitignore`
  - Replaced operator username and `/home/doubl/` paths with `<operator>` placeholders across systemd units, docker-compose files, and gateway manifest
  - Replaced internal subnet `192.168.1.0/24` with `<INTERNAL_SUBNET>/24` in firewall baseline and architecture docs
  - Local docker-compose files restored with real paths via `git skip-worktree`

## 2026-03-19
- Removed "Model & Settings Guidance" section from .claude/CLAUDE.md (cross-repo cleanup)

## 2026-03-19
- Removed "Model & Settings Guidance" section from .claude/CLAUDE.md (cross-repo cleanup)
