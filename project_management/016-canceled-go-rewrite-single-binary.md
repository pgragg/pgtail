# 016 — Go rewrite for single-binary distribution (post-v1)

**Status:** Canceled
**Priority:** Low

> Canceled: Python version is the canonical implementation.
**Estimate:** XL

## Goal
Once the Python version is feature-stable, port to Go for `brew install pgtail` / `curl | sh` distribution with no Python dependency.

## Tasks
- [ ] Evaluate `jackc/pglogrepl` for pgoutput decoding
- [ ] Port feature-by-feature with parity tests
- [ ] GoReleaser for cross-platform binaries
- [ ] Homebrew tap

## Notes
Only pursue if there's clear demand. Python version remains the reference implementation.
