# 004 — Logical replication stream (pgoutput)

**Status:** Todo
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
