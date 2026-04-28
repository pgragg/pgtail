# 008 — Persistent slot mode

**Status:** Done
**Priority:** Low
**Estimate:** S

## Goal
Allow long-lived replication slots for users who want continuity across restarts.

## Tasks
- [ ] `--slot NAME` reuses an existing slot or creates a permanent one
- [ ] Print prominent warning about WAL retention risk if the tool isn't running
- [ ] On Ctrl-C: do NOT drop the slot, just disconnect cleanly
- [ ] `pgtail --drop-slot NAME` helper to remove it later

## Acceptance
- Running with `--slot foo`, killing, restarting → resumes from last confirmed LSN, no missed events
- Without `--slot`, behavior is ephemeral (default)

## Completion notes
- The slot reuse / persistence path was already wired in ticket 004's `_setup_publication_and_slot`: when `settings.slot` is set, the slot is created with `temporary=False` (or reused if it already exists), and cleanup skips dropping it.
- Added a yellow startup warning when running with `--slot` reminding the user that WAL accumulates while pgtail isn't running, plus a hint at how to drop the slot.
- Added a `drop_slot(dsn, name)` helper in `pgtail/replication.py` that checks `pg_replication_slots` and calls `pg_drop_replication_slot()`. Returns whether the slot existed.
- New `--drop-slot NAME` CLI flag short-circuits the normal flow: when present, pgtail drops the named slot and exits 0 (or 2 on error / missing DSN). Note: due to Typer/click parsing, the flag should appear before the positional DSN (`pgtail --drop-slot myslot $DATABASE_URL`).
- Acknowledgment LSN is sent on every commit and on a 10s heartbeat (already wired in ticket 004), so a persistent slot won't drift far before being advanced.
- Added 3 CLI tests using monkeypatched `drop_slot`. Total suite: 77 passing.
