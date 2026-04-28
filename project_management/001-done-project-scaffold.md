# 001 — Project scaffold

**Status:** Done
**Priority:** High
**Estimate:** S

## Goal
Stand up the Python project skeleton so subsequent tickets have a place to land.

## Tasks
- [ ] Create repo `pgtail` with `pyproject.toml` (Python 3.11+, `psycopg[binary]`, `click` or `typer`, `rich` for color)
- [ ] Configure `pipx`-installable entry point: `pgtail = pgtail.cli:main`
- [ ] Add `ruff` + `mypy` configs
- [ ] Add `pytest` setup with one smoke test
- [ ] Add `.editorconfig`, `.gitignore`, MIT `LICENSE`
- [ ] Stub `pgtail/cli.py`, `pgtail/replication.py`, `pgtail/format.py`, `pgtail/filters.py`

## Acceptance
- `pipx install -e .` works locally
- `pgtail --help` prints usage
- `pytest` passes

## Completion notes
- Used `hatchling` as the build backend; `uv venv` + `uv pip install -e ".[dev]"` confirmed working with Python 3.11.
- Stack: `psycopg[binary]`, `typer`, `rich`. Dev deps: `pytest`, `pytest-cov`, `ruff`, `mypy`, `testcontainers[postgres]`.
- Files created: `pyproject.toml`, `.gitignore`, `.editorconfig`, `LICENSE` (MIT), `README.md`, `pgtail/{__init__,cli,replication,format,filters}.py`, `tests/{__init__,test_smoke}.py`.
- Entry point `pgtail = pgtail.cli:main` works; `pgtail --help` and `pgtail --version` both verified.
- `pytest` (3 smoke tests) passes; `ruff check` and `ruff format --check` clean.
