# 010 — Tests & CI

**Status:** Todo
**Priority:** High
**Estimate:** M

## Goal
Confidence that pgtail works against real Postgres versions.

## Tasks
- [ ] Unit tests: pgoutput message parser (use captured byte fixtures)
- [ ] Unit tests: formatter (golden-output tests for each op)
- [ ] Unit tests: filter glob matching, redaction
- [ ] Integration tests: spin up Postgres via `testcontainers-python`, run real INSERT/UPDATE/DELETE, assert events
- [ ] GitHub Actions matrix: Postgres 14, 15, 16, 17 × Python 3.11, 3.12
- [ ] Lint job: `ruff check`, `ruff format --check`, `mypy`
- [ ] Coverage report (target ≥80%)

## Acceptance
- CI green on PRs
- `pytest` runs locally with Docker available
