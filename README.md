# pgtail

**Tail Postgres row changes (INSERT / UPDATE / DELETE) with color in your terminal,
via logical replication.** No triggers. No schema changes. Read-only on your DB.

```text
14:02:11  INSERT  public.users          {id: 42, email: "ana@b.com", name: "Ana"}
14:02:11  UPDATE  public.users  email   "ana@b.com" → "ana@example.com"
14:02:12  DELETE  public.users          {id: 42, email: "ana@example.com", name: "Ana"}
```

> Why pgtail? `psql` shows you state. `pgtail` shows you *changes* — what your
> app, your migrations, and your background workers are actually doing to the
> database, live, while you watch.

## 30-second quickstart

```bash
# 1. Install (PyPI distribution name is `pgtail-cdc`; the installed command is `pgtail`)
uv tool install pgtail-cdc        # or: pipx install pgtail-cdc / pip install pgtail-cdc

# Note: an unrelated, older package named `pgtail` (by Chillar Anand) exists on
# PyPI — it polls a single table with SELECT. This project is a different tool
# that streams INSERT/UPDATE/DELETE via logical replication, so it ships under
# a distinct name to avoid collision.

# 2. Make sure Postgres has logical replication on (one-time, see below)

# 3. Tail it
pgtail postgresql://user:pw@localhost:5432/mydb
```

That's it. Make a change in another window — `INSERT INTO users …` — and watch
it scroll by.

If `$DATABASE_URL` is set, you can drop the DSN argument entirely:

```bash
pgtail
```

## Requirements

- **Postgres ≥ 14**
- `wal_level = logical` on the server
- A role with the `REPLICATION` attribute and connect access to the target DB
- Python 3.11+ on the client (your laptop)

`pgtail` uses Postgres's built-in `pgoutput` logical decoder — **no server-side
extensions or plugins to install**, which means it works against managed
Postgres providers and locked-down staging boxes alike.

## Configuring Postgres for logical replication

If you control the server, this is a one-time change:

```sql
-- As a superuser
ALTER SYSTEM SET wal_level = 'logical';
ALTER SYSTEM SET max_replication_slots = 10;
ALTER SYSTEM SET max_wal_senders = 10;
-- Then restart Postgres for wal_level to take effect.

-- Grant REPLICATION to the role you'll connect as:
ALTER ROLE myuser WITH REPLICATION;
```

Verify:

```sql
SHOW wal_level;        -- expect: logical
SELECT rolreplication FROM pg_roles WHERE rolname = current_user;  -- expect: t
```

`pgtail` runs a preflight check on startup and prints a clear error if either
of these is wrong.

### Managed providers

| Provider          | How to enable logical replication                                         |
|-------------------|---------------------------------------------------------------------------|
| **AWS RDS / Aurora** | Set parameter group `rds.logical_replication = 1`, reboot. Grant `rds_replication` to the role. |
| **Google Cloud SQL** | Set the `cloudsql.logical_decoding` flag to `on`, restart instance. Use a role with `REPLICATION`. |
| **Azure Database for PostgreSQL** | Server parameter `wal_level = LOGICAL`, restart. Use the `azure_pg_admin` role or one with `REPLICATION`. |
| **Supabase**      | Already on by default. Use the project's database role.                  |
| **Neon**          | Already on by default. Use a role granted `REPLICATION`.                |
| **Heroku Postgres** | Standard / Premium / Private tiers only. Contact support to enable.    |

## Common flags

```text
pgtail [DSN]
  --schema public,sales        # comma-separated schema include list
  --tables 'order_*,users'     # glob include list
  --exclude '*_audit'          # glob exclude list
  --ops insert,update,delete   # which operations to show
  --json                       # one JSON object per change (pipe-friendly)
  --no-color                   # disable ANSI colors (also: NO_COLOR=1)
  --no-time                    # hide the HH:MM:SS column
  -v / --verbose               # include txid and LSN on every line
  --max-width 120              # truncate long values
  --redact password,token      # mask these column values as ***
  --slot pgtail_dev            # persistent slot (resume on restart)
  --drop-slot pgtail_dev       # cleanup helper for persistent slots
  --log-file changes.log       # tee plain output to a file
  --expand-all                 # don't collapse big transactions
  --collapse-threshold 1000    # rows-per-(op,table) before collapsing
  --config ./.pgtail.toml      # config file path (auto-discovered too)
```

Run `pgtail --help` for the complete list.

## Config file

`pgtail` auto-discovers `./.pgtail.toml` in the current directory, then
`~/.config/pgtail/config.toml`. CLI flags always win over config-file values.

```toml
# .pgtail.toml
dsn = "postgresql://dev:dev@localhost:5432/myapp"

schemas = ["public", "billing"]
tables  = ["users", "orders", "order_*"]
exclude = ["*_audit", "schema_migrations"]
ops     = ["insert", "update", "delete"]

json    = false
verbose = true
redact  = ["password", "password_hash", "api_key", "stripe_secret"]

slot              = "pgtail_dev"
collapse_threshold = 5000
max_width         = 120
```

## Examples

```bash
# Watch only the orders schema, skip audit tables
pgtail --schema orders --exclude '*_audit'

# Pipe JSON into jq
pgtail --json --no-color | jq 'select(.op == "update")'

# Tee a debug log while still watching colorized output
pgtail --log-file /tmp/pgtail.log

# Resume across restarts (uses a persistent slot — see "Persistent slots" below)
pgtail --slot myteam_pgtail
# When done, free the slot so it stops retaining WAL:
pgtail --drop-slot myteam_pgtail
```

## Persistent slots — important

By default `pgtail` creates an **ephemeral** replication slot per session and
drops it on exit. That's safe: no WAL retention beyond your session.

`--slot NAME` switches to a **persistent** slot. The server then retains WAL
from your slot's confirmed position until you either consume it or drop the
slot. **A forgotten persistent slot will eventually fill the disk.** Use
`--drop-slot NAME` (or `SELECT pg_drop_replication_slot('NAME')`) when you're
done.

## Does this modify my database?

**No.**

- `pgtail` does not create triggers.
- `pgtail` does not write to user tables.
- The only server-side state it creates is a `PUBLICATION` and a
  `REPLICATION SLOT`, both with names prefixed `pgtail_`. Both are dropped
  on clean exit (the publication unconditionally; the slot when ephemeral).
- It uses the same protocol your standby replicas and CDC pipelines use.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `wal_level must be 'logical', got 'replica'` | Server not configured for logical decoding | `ALTER SYSTEM SET wal_level = 'logical'` and restart |
| `role "x" does not have REPLICATION attribute` | Connection role can't open replication streams | `ALTER ROLE x WITH REPLICATION` |
| `must be superuser or replication role to start walsender` | RDS/Aurora needs `rds_replication` | `GRANT rds_replication TO x` |
| `replication slot "pgtail_xxx" already exists` | Previous run crashed before cleanup | Drop it: `pgtail --drop-slot pgtail_xxx` |
| Disk filling up after using `--slot` | A persistent slot is retaining WAL | Drop unused slots; check `pg_replication_slots` |
| `terminating walsender process due to replication timeout` | Network blip or paused consumer | pgtail sends keepalives every 10s; if your `wal_sender_timeout` is < 30s, raise it |
| `No DSN provided and $DATABASE_URL is unset` | Missing connection string | Pass a DSN argument or export `DATABASE_URL` |
| `pgtail` shows no events | Wrong schema/table filter, or workload is on a non-published table | Drop `--tables`/`--schema` filters; confirm `pg_publication_tables` |

## How it works (one paragraph)

`pgtail` opens a regular Postgres connection, creates a temporary
`PUBLICATION FOR ALL TABLES` (or a filtered one if you passed `--tables`),
creates a logical replication slot using the built-in `pgoutput` decoder, and
then opens a second connection in **replication mode** to call
`START_REPLICATION SLOT … LOGICAL …`. It decodes the binary `pgoutput`
protocol client-side, mapping each `Insert`/`Update`/`Delete` message back to
the relation's column metadata, and renders the result with `rich`. Filters
and redaction run client-side, so they never affect what the server publishes.

## Development

```bash
git clone …
cd 00_pgtail
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

pytest -m "not integration"               # fast unit tests
PGTAIL_TEST_DSN=postgresql://… pytest    # also run the integration test
ruff check . && ruff format --check .
```

The integration test will, by default, spin up a Postgres container via
`testcontainers`. Set `PGTAIL_TEST_DSN` to point at any Postgres with
`wal_level=logical` to skip Docker (this is what CI does).

## License

MIT.
