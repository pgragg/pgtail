# 002 — Connection handling & CLI args

**Status:** Done
**Priority:** High
**Estimate:** S

## Goal
Accept a Postgres connection string and the core CLI flags.

## Tasks
- [ ] Positional arg: connection URL (`postgresql://...`)
- [ ] Fallback to `DATABASE_URL` env var if no arg provided
- [ ] Flags: `--tables`, `--exclude`, `--schema` (default `public`), `--ops` (default `insert,update,delete`)
- [ ] Flags: `--json`, `--no-color`, `--no-time`, `--verbose`, `--max-width` (default 80)
- [ ] Flags: `--redact` (default list: `password,password_hash,api_key,secret,token`)
- [ ] Flags: `--slot NAME` (persistent), `--log-file PATH`
- [ ] Respect `NO_COLOR` env var
- [ ] Validate connection on startup; print friendly error if unreachable

## Acceptance
- `pgtail --help` lists every flag with sensible help text
- Bad URL → clean error, exit 2

## Completion notes
- Added `pgtail/options.py` with frozen `Settings` dataclass (DSN, schemas, tables, exclude, ops, output flags, redact, slot, log_file, large-txn settings) and helpers `parse_ops`, `parse_csv_tuple`, `Settings.resolve_dsn`, `Settings.resolve_color`.
- Added `pgtail/connection.py` with `validate_connection(dsn)` performing a brief `psycopg.connect` + `SELECT current_database/user/server_version_num`.
- Rewrote `pgtail/cli.py` as a single Typer callback (`invoke_without_command=True`) so `pgtail --help` shows the program name. All v1 flags wired: `--schema`, `--tables`, `--exclude`, `--ops`, `--json`, `--no-color`, `--no-time`, `--verbose`, `--max-width`, `--redact`, `--slot`, `--log-file`, `--expand-all`, `--collapse-threshold`, `--version`.
- DSN resolution: positional arg → `$DATABASE_URL` → friendly error (exit 2). Bad URL shape, unreachable host, and invalid `--ops` all exit 2 with red error message.
- Honors `NO_COLOR` env var per https://no-color.org.
- Added `tests/test_cli_args.py` with 13 tests covering help output, DSN fallback, error paths, op parsing, CSV parsing, NO_COLOR handling. Total suite: 16 passing.
