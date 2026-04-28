# 007 — Large transaction handling

**Status:** Todo
**Priority:** Medium
**Estimate:** S

## Goal
Avoid drowning the terminal on bulk operations.

## Tasks
- [ ] Track per-statement row count within a transaction
- [ ] If a single op on a single table exceeds 1000 rows, collapse remaining events into a summary line: `UPDATE public.users  1,247 rows (collapsed)`
- [ ] `--expand-all` flag bypasses collapsing
- [ ] Threshold configurable via `--collapse-threshold N` (default 1000)

## Acceptance
- `UPDATE users SET active = true;` on a 10k-row table shows a single collapsed summary
- `--expand-all` shows every row
