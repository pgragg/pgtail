# 004 — Logical replication stream (pgoutput)

**Status:** Done
**Priority:** High
**Estimate:** L

## Goal
Connect via psycopg3's replication API, create a temp slot + publication, and decode `pgoutput` messages into structured change events.

## Tasks
- [ ] Create ephemeral publication `pgtail_pub_<rand>` for selected tables (or `FOR ALL TABLES` if no filter)
- [ ] Create temp logical replication slot `pgtail_<rand>` with `pgoutput`
- [ ] `START_REPLICATION SLOT ... LOGICAL` with `proto_version=1`, `publication_names=...`
- [ ] Implement pgoutput binary message parser:
  - [ ] `Begin` / `Commit` (txid + commit LSN)
  - [ ] `Relation` (cache table OID → schema.name + column metadata)
  - [ ] `Insert` / `Update` / `Delete` / `Truncate`
- [ ] Decode tuple data using cached relation metadata + Postgres type OIDs
- [ ] Yield typed `ChangeEvent` objects (op, schema, table, txid, ts, new_row, old_row)
- [ ] Send periodic `Standby Status Update` to keep slot alive
- [ ] On Ctrl-C: stop stream, drop slot, drop publication, exit 0

## Acceptance
- Inserting/updating/deleting rows in `psql` produces a stream of `ChangeEvent`s in real time
- Ctrl-C leaves zero leftover slots/publications (`SELECT * FROM pg_replication_slots` is clean)

## References
- psycopg3 logical replication docs
- Postgres pgoutput message format spec

## Completion notes
- Added `pgtail/events.py` with `ChangeEvent`, `RelationMeta`, `ColumnMeta` dataclasses.
- Added `pgtail/pgoutput.py` — pure pgoutput v1 decoder (no I/O). Handles Begin/Commit/Origin/Type/Relation/Insert/Update/Delete/Truncate; handles `K`/`O`/`N` tuple markers and `n`/`u`/`t`/`b` column kinds. `_UNCHANGED` sentinel for TOASTed unchanged columns.
- `decode_value()` returns typed Python values for ints, floats, numerics, bools, and json (raw text); falls back to UTF-8 string for unknown OIDs.
- Added `pgtail/replication.py` — `stream_changes(settings)` generator:
  - Creates `pgtail_pub_<rand>` (FOR ALL TABLES, or restricted to resolved table list when `--tables` is set) and a temp logical slot `pgtail_<rand>` with the `pgoutput` plugin (or reuses `--slot NAME` when persistent).
  - Opens a second connection with `replication="database"`, issues `START_REPLICATION SLOT ... LOGICAL 0/0 (proto_version '1', publication_names '...')`, and reads the COPY stream.
  - Parses replication-protocol framing (XLogData `w`, Keepalive `k`), feeds payloads to `decode_message`, maintains a relation cache, computes `changed_fields` for UPDATEs, and yields `ChangeEvent`s.
  - Sends `Standby Status Update` (`r`) on commit and on a 10s heartbeat so the slot doesn't fall behind. Replies immediately when keepalive requests it.
  - On generator exit (Ctrl-C, break, exception): drops the publication and the slot if it was ephemeral.
- CLI now invokes `stream_changes()` after preflight; Ctrl-C exits 0 with a friendly message.
- Added 17 unit tests (`tests/test_pgoutput.py`, `tests/test_replication_helpers.py`) using synthesized byte fixtures — no live DB required. Total suite: 44 passing.
- Live integration tests (real psql INSERT/UPDATE/DELETE) are deferred to ticket 010 where `testcontainers` will spin up a real Postgres.
