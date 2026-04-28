# 011 — Docs & README

**Status:** Todo
**Priority:** High
**Estimate:** S

## Goal
Make it trivial for a new user to get pgtail running in 30 seconds.

## Tasks
- [ ] README with:
  - [ ] Animated GIF / asciinema demo
  - [ ] 30-second quickstart (install + run)
  - [ ] `wal_level=logical` setup snippet
  - [ ] Managed-provider notes (RDS, Supabase, Neon, Cloud SQL)
  - [ ] Full flag reference
  - [ ] Example `.pgtail.toml`
  - [ ] Troubleshooting section (common errors → fixes)
  - [ ] FAQ: "does this modify my DB?" (no triggers, read-only)
- [ ] CHANGELOG.md
- [ ] CONTRIBUTING.md

## Acceptance
- A teammate with no prior context can install and see colored events within 30 seconds on a local Postgres
