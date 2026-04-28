# 00_pgtail

A colored CLI that tails Postgres row changes (INSERT/UPDATE/DELETE) via logical replication.

## Tech Stack
- Python 3.11+
- `psycopg[binary]` v3 (native logical replication support)
- `pgoutput` built-in plugin (no extensions required)
- Distributed via `pipx` / `pip`

## Status Conventions
Tickets use Linear's default statuses in the filename prefix:
- `backlog` — Not yet planned
- `todo` — Planned, ready to pick up
- `in-progress` — Actively being worked on
- `in-review` — PR open / awaiting review
- `done` — Merged / shipped
- `canceled` — Won't do

Format: `NNN-status-short-slug.md`

## Tickets
See individual `.md` files in this folder.
