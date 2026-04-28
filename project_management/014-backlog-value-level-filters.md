# 014 — Value-level filters (post-v1)

**Status:** Backlog
**Priority:** Low
**Estimate:** M

## Goal
Filter events by row content, e.g. `--where 'users.id=42'` or `--where 'orders.total>100'`.

## Tasks
- [ ] Mini expression parser (eq, neq, gt, lt, in, like)
- [ ] Apply per-table filters client-side after decoding
- [ ] Document performance caveat (filtering happens after decode, not in Postgres)

## Notes
Explicitly out of v1.
