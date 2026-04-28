# 003 — Preflight: wal_level & permissions check

**Status:** Todo
**Priority:** High
**Estimate:** S

## Goal
Detect missing prerequisites and tell the user exactly how to fix them.

## Tasks
- [ ] Query `SHOW wal_level;` — fail fast if not `logical`
- [ ] Check current role has `REPLICATION` attribute (`pg_roles`)
- [ ] If missing, print copy-pasteable fix:
  ```
  ALTER SYSTEM SET wal_level = logical;
  -- then restart Postgres
  ALTER ROLE myuser WITH REPLICATION;
  ```
- [ ] Detect managed-provider hints (RDS, Supabase, Neon) from hostname and link to provider-specific docs
- [ ] Exit code 3 for preflight failure (distinct from connection failure)

## Acceptance
- Running against a stock local Postgres with `wal_level=replica` shows a clear, actionable error
