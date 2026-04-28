# Contributing to pgtail

Thanks for your interest! pgtail is intentionally small: a focused CLI for
tailing Postgres logical-replication changes. Contributions that keep that
scope tight are very welcome.

## Project layout

```
pgtail/
  cli.py            # typer entrypoint
  options.py        # Settings dataclass, CSV parsers
  config.py         # .pgtail.toml loader
  connection.py     # DSN validation
  preflight.py      # wal_level + REPLICATION attribute checks
  replication.py    # publication/slot lifecycle + pgoutput stream loop
  pgoutput.py       # pure decoder for the pgoutput binary protocol
  events.py         # ChangeEvent dataclass
  filters.py        # client-side schema/table/op filtering
  format.py         # rich-based renderer + JSON renderer
  collapse.py       # large-transaction collapsing
tests/
  test_*.py         # unit tests (no DB required)
  test_integration.py  # spins up Postgres or uses PGTAIL_TEST_DSN
project_management/
  NNN-*.md          # ticket-by-ticket development log
```

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

(If you don't have `uv`: `python -m venv .venv && pip install -e ".[dev]"`.)

## Running tests

```bash
# Fast: unit tests only
pytest -m "not integration"

# All tests, using a Postgres you already have running
PGTAIL_TEST_DSN=postgresql://postgres:pw@localhost:5432/postgres pytest

# All tests, letting testcontainers spin one up (needs Docker)
pytest
```

## Lint / format / types

```bash
ruff check .
ruff format --check .
mypy pgtail        # advisory in CI; please don't make it worse
```

## Style notes

- Pure functions where possible. The `pgoutput`, `format`, `filters`,
  `collapse`, and `config` modules deliberately have **zero** I/O so they
  remain easy to unit-test from byte fixtures.
- Prefer adding behavior client-side over creating new server-side state.
  We never want pgtail to need a trigger, a new role, or anything beyond a
  publication and a slot.
- New CLI flags belong in `pgtail/options.py` (the `Settings` dataclass) and
  `pgtail/cli.py`. Keep defaults sensible for "I just want to see what's
  changing right now."

## Pull request checklist

- [ ] Added or updated tests
- [ ] `pytest -m "not integration"` passes locally
- [ ] `ruff check .` and `ruff format --check .` clean
- [ ] Updated `CHANGELOG.md` under `[Unreleased]`
- [ ] Updated `README.md` if you touched user-visible behavior

## Reporting bugs

Please include:

- pgtail version (`pgtail --version`)
- Postgres version (`SELECT version();`)
- The DSN shape (`postgresql://user@host:port/db` — feel free to redact)
- The first ~20 lines of `pgtail -v` output, or the full error if it crashed

Replication bugs are often subtle and depend on `wal_level`, replica identity,
and the role's `REPLICATION` attribute — please mention those.

## License

By contributing, you agree that your contributions will be licensed under
the project's MIT license.
