# 006 — Filters & redaction

**Status:** Done
**Priority:** Medium
**Estimate:** S

## Goal
Apply the user's `--tables`, `--exclude`, `--schema`, `--ops`, and `--redact` selections.

## Tasks
- [ ] Glob matching for `--tables` / `--exclude` (e.g. `order_*`, `*_log`)
- [ ] Build publication's table list from include/exclude rules; if empty post-filter, use `FOR ALL TABLES` and filter client-side
- [ ] Drop events whose op isn't in `--ops`
- [ ] Hide system schemas (`pg_catalog`, `information_schema`) by default
- [ ] Redaction: replace value with `***` for any column name matching `--redact` list (case-insensitive)
- [ ] Default redact list: `password, password_hash, api_key, secret, token`

## Acceptance
- `--tables users` only shows `users` events
- `--exclude '*_log'` hides `audit_log`, `event_log`
- `--ops update` shows only updates
- Redacted columns render as `password: ***` even in `--json`

## Completion notes
- Added `pgtail/filters.py` with pure predicates: `schema_allowed`, `table_allowed`, `op_allowed`, composite `event_allowed`, plus `redact_set` and a `SYSTEM_SCHEMAS` constant (`pg_catalog`, `information_schema`, `pg_toast`).
- Glob matching uses `fnmatch.fnmatchcase` so patterns like `order_*` and `*_log` work.
- Exclude rules win over include rules; system schemas are hidden unless the user explicitly opts in via `--schema`.
- TRUNCATE events are kept if any of their `truncated_tables` matches the include/exclude rules.
- Publication-side filtering (already implemented in `replication._resolve_tables`) covers `--tables`; client-side filtering covers `--exclude` (CREATE PUBLICATION lacks EXCLUDE) and system-schema hiding.
- Redaction in renderer (text + JSON) was completed in ticket 005; this ticket adds the `redact_set` helper for any future call sites.
- CLI swaps the trivial `event.op not in settings.ops` check for `event_allowed(event, settings)`.
- Added 12 filter tests. Total suite: 68 passing.
