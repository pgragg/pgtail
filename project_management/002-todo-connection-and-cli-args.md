# 002 — Connection handling & CLI args

**Status:** Todo
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
