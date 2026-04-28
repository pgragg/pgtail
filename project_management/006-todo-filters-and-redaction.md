# 006 — Filters & redaction

**Status:** Todo
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
