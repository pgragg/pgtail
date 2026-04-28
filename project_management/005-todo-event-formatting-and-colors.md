# 005 — Event formatting & colors

**Status:** Todo
**Priority:** High
**Estimate:** M

## Goal
Render `ChangeEvent`s as the colored, human-readable lines described in the spec.

## Tasks
- [ ] INSERT → green `INSERT schema.table {field: value, ...}`
- [ ] DELETE → red `DELETE schema.table {field: value, ...}`
- [ ] UPDATE → yellow `UPDATE schema.table id=X  field: old → new` (only changed fields)
- [ ] TRUNCATE → magenta `TRUNCATE schema.table`
- [ ] Optional leading timestamp `HH:MM:SS` (toggle `--no-time`)
- [ ] `--verbose` adds `txid=… lsn=…`
- [ ] Truncate long values to `--max-width` with `…`
- [ ] JSON renderer (`--json`) emits one compact JSON object per line
- [ ] Plain renderer when `--no-color` or non-TTY stdout
- [ ] `--log-file` writes plain (no-ANSI) copy in parallel

## Acceptance
- Visual check matches the spec example output
- `pgtail --json | jq .` works
- Piping to a file produces no ANSI escape codes
