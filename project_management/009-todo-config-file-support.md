# 009 — Config file support (.pgtail.toml)

**Status:** Todo
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
