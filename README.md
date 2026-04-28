# pgtail

Tail Postgres row changes (INSERT / UPDATE / DELETE) with color in your terminal,
via logical replication. No triggers. Read-only.

> Status: scaffold. See `project_management/` for ticket-by-ticket progress.

## Quickstart (dev)

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pgtail --help
```

## Requirements
- Postgres 14+ with `wal_level = logical`
- A role with the `REPLICATION` attribute
