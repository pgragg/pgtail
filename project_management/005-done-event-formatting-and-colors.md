# 005 — Event formatting & colors

**Status:** Done
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

## Completion notes
- Added `Renderer` class in `pgtail/format.py` built on `rich.Console` for ANSI output and `json.dumps` for `--json`.
- Op colors: green INSERT, yellow UPDATE, red DELETE, magenta TRUNCATE.
- INSERT/DELETE render `{field: value, ...}` style; UPDATE renders `id=N  field: old → new` for changed fields only.
- Long values truncated to `--max-width` (default 80) with a trailing `…`.
- Strings rendered with quotes; numbers/bools/null without; `<unchanged>` sentinel surfaces TOASTed columns the publisher couldn't include.
- `--no-time` hides the `HH:MM:SS` prefix; `--verbose` adds `txid=... lsn=...`.
- Auto-disables color when stdout isn't a TTY or when `--no-color`/`NO_COLOR` is set.
- `--json` emits one compact JSON object per line (`ts`, `op`, `schema`, `table`, optional `txid`/`lsn`, `new`/`old`, `changed`, or `tables` for truncate). Redacted columns become `***` in both text and JSON output.
- `--log-file PATH` opens the file in append mode and writes ANSI-stripped copies of each line in parallel; closed cleanly on exit.
- CLI now drives the renderer (with op-level filtering); replaces the placeholder repr.
- Added 13 formatter tests (`tests/test_format.py`). Total suite: 56 passing.
