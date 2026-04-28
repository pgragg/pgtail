# Changelog

All notable changes to `pgtail` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
intends to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once a `1.0.0` is cut.

## [Unreleased]

### Added
- Initial implementation of `pgtail`:
  - CLI built with `typer`, colorized output via `rich`.
  - Logical replication via Postgres's built-in `pgoutput` decoder; no
    server-side extensions required.
  - Filters: `--schema`, `--tables`, `--exclude`, `--ops`.
  - Per-column redaction with sensible defaults (`password`,
    `password_hash`, `api_key`, …).
  - Large-transaction collapsing (`--collapse-threshold`, `--expand-all`).
  - Persistent replication slots (`--slot`) with a cleanup helper
    (`--drop-slot`).
  - TOML config-file support with auto-discovery
    (`./.pgtail.toml`, `~/.config/pgtail/config.toml`).
  - JSON output mode for piping (`--json`).
  - Optional plain-text tee (`--log-file`).
- Unit tests for the pgoutput parser, formatter, filters, redaction,
  collapse, config, and CLI argument plumbing.
- Integration test that drives a real Postgres INSERT/UPDATE/DELETE through
  `stream_changes` and asserts the event sequence.
- GitHub Actions CI: lint job + Python {3.11, 3.12} × Postgres {14, 15, 16, 17}
  matrix.

### Fixed
- `psycopg3`'s `pgconn.get_copy_data(async_)` returns a
  `(nbytes, memoryview)` tuple. The streaming loop previously treated the
  tuple as bytes, corrupting every replication row. Now destructured and
  dispatched on `nbytes`.
- Replication slots are created as permanent at the SQL layer and dropped on
  exit when ephemeral. Postgres's "temporary" slots are tied to the SQL
  session that creates them, so they would vanish before the replication
  connection ever opened.
