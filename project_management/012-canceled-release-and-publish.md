# 012 — Release & publish to PyPI

**Status:** Canceled
**Priority:** Medium

> Canceled: not publishing to PyPI for now. Local install via `pipx install -e .` is sufficient.
**Estimate:** S

## Goal
Ship v0.1.0.

## Tasks
- [ ] Tag `v0.1.0`
- [ ] GitHub Actions release workflow: build sdist + wheel, publish to PyPI via trusted publishing (OIDC)
- [ ] Verify `pipx install pgtail` works from clean machine
- [ ] Create GitHub Release with changelog notes + demo GIF
- [ ] Post in relevant communities (r/PostgreSQL, HN Show, Lobsters) — optional

## Acceptance
- `pipx install pgtail` from PyPI yields a working binary
- v0.1.0 release page is live
