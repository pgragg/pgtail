# 007 — Large transaction handling

**Status:** Done
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

## Completion notes
- Added `pgtail/collapse.py` with the `Collapser` class. Tracks per `(txid, qualified_table, op)` counts; once `count > collapse_threshold`, subsequent matching events are swallowed and a one-time inline notice is emitted (`… collapsing remainder after N rows`). When the txid changes (next transaction begins) or `flush()` is called at shutdown, a summary event `{collapsed_count: N}` is emitted.
- TRUNCATE events never collapse.
- `--expand-all` short-circuits the collapser into a passthrough.
- Renderer (`pgtail/format.py`) recognizes the synthesized events: text mode shows `UPDATE public.users  10,000 rows (collapsed)` in dim italic; JSON mode emits `{ ..., "collapsed_count": 10000 }` (or `{ ..., "collapse_notice": true, "threshold": 1000 }` for the inline notice).
- CLI runs each event through filters → collapser → renderer; `collapser.flush()` is called after the stream ends so dangling summaries are not lost.
- Added 6 collapser tests covering passthrough, threshold trigger, expand_all, per-table/op grouping, txid rollover flush, and truncate behavior. Total suite: 74 passing.
