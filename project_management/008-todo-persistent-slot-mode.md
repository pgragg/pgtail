# 008 — Persistent slot mode

**Status:** Todo
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
