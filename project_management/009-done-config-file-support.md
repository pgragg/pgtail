# 009 — Config file support (.pgtail.toml)

**Status:** Done
**Priority:** Low
**Estimate:** S

## Goal
Let users save common flag combinations.

## Tasks
- [ ] Look for `./.pgtail.toml`, then `~/.config/pgtail/config.toml`
- [ ] Schema: `[default]` section with same keys as CLI flags
- [ ] Precedence: CLI flag > env var > config file > built-in default
- [ ] `--config PATH` to point at a specific file
- [ ] Document example config in README

## Acceptance
- A `.pgtail.toml` with `tables = ["users", "orders"]` is honored
- CLI flag overrides config file value

## Completion notes
- Added `pgtail/config.py` with `load_config(explicit_path=None)`. Lookup order: explicit `--config PATH` → `./.pgtail.toml` → `~/.config/pgtail/config.toml`. Uses stdlib `tomllib` (Python 3.11+).
- Schema: `[default]` table with the same names as CLI flags (snake-case for hyphenated ones, e.g. `max_width`). Lists are accepted for CSV-style options (`tables`, `exclude`, `redact`, `schema`, `ops`) and joined into the comma-separated form the CLI parsers expect.
- Added `--config PATH` flag to the CLI.
- Precedence is enforced via `click.core.ParameterSource`: for each option, if Click reports the source as `DEFAULT`, the config value (when present) overrides it. CLI-provided and env-provided values win unchanged.
- `ConfigError` is raised on missing explicit paths, malformed TOML, or wrong shape; surfaced as red exit-2 errors.
- Added 7 config tests covering load behavior and CLI precedence (using monkeypatched `validate_connection`/`run_preflight`/`stream_changes` so no live DB is needed). Total suite: 85 passing.
- README example will be added in ticket 011.
