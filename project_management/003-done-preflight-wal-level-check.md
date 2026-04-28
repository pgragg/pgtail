# 003 — Preflight: wal_level & permissions check

**Status:** Done
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

## Completion notes
- Added `pgtail/preflight.py` with `run_preflight(dsn)` returning a `PreflightInfo` and raising `PreflightError` (exit code 3) on failure.
- Checks performed: `SHOW wal_level` (must be `logical`); `SELECT rolreplication FROM pg_roles WHERE rolname = current_user` (must be true).
- Failure messages include copy-pasteable SQL: `ALTER SYSTEM SET wal_level = 'logical';` (with restart note) and `ALTER ROLE <user> WITH REPLICATION;`.
- `detect_provider()` recognizes RDS, Supabase, Neon, Cloud SQL, Azure, Render, Railway from the DSN hostname and appends a docs link.
- CLI wired to call `run_preflight` after `validate_connection`, exit code 3 on preflight failure (vs 2 for connection failure).
- Added `tests/test_preflight.py` with 9 unit tests (hostname parsing, provider detection, fix-text contents). Total suite: 25 passing.
