# 011 — Docs & README

**Status:** Done
**Priority:** High
**Estimate:** S

## Goal
Make it trivial for a new user to get pgtail running in 30 seconds.

## Tasks
- [ ] README with:
  - [ ] Animated GIF / asciinema demo
  - [ ] 30-second quickstart (install + run)
  - [ ] `wal_level=logical` setup snippet
  - [ ] Managed-provider notes (RDS, Supabase, Neon, Cloud SQL)
  - [ ] Full flag reference
  - [ ] Example `.pgtail.toml`
  - [ ] Troubleshooting section (common errors → fixes)
  - [ ] FAQ: "does this modify my DB?" (no triggers, read-only)
- [ ] CHANGELOG.md
- [ ] CONTRIBUTING.md

## Acceptance
- A teammate with no prior context can install and see colored events within 30 seconds on a local Postgres

## Completion notes

- **README.md** rewritten end-to-end. Includes:
  - 30-second quickstart (`uv tool install pgtail` → `pgtail $DATABASE_URL`).
  - `wal_level=logical` setup snippet with verification queries.
  - Managed-provider matrix (RDS/Aurora, Cloud SQL, Azure, Supabase, Neon,
    Heroku) with the exact flag/parameter to flip on each.
  - Full flag reference (mirrors `pgtail --help`).
  - Example `.pgtail.toml` covering schemas/tables/exclude/ops, redaction,
    persistent slot, max_width, collapse threshold.
  - Troubleshooting table (8 common errors → fixes).
  - FAQ paragraph: "Does this modify my database?" with a clear no.
  - Persistent-slot warning (forgotten slots fill the disk) + drop-slot
    pointer.
  - One-paragraph "how it works" for curious readers.
- **CHANGELOG.md** created with a single `[Unreleased]` entry covering all
  features built across tickets 001–010 plus the two notable fixes from 010
  (the `get_copy_data` tuple bug and the permanent-slot lifetime fix).
- **CONTRIBUTING.md** created with project layout, setup, test/lint commands,
  style notes (pure-function preference, no new server-side state), and a PR
  checklist.
- Animated GIF / asciinema demo intentionally **deferred** (would need a
  recording session and an asset path; better to add post-release once the
  CLI's exact output stabilizes). Replaced with an inline ASCII example at
  the top of the README that conveys the same impression.

### Files touched
- `README.md` (full rewrite)
- `CHANGELOG.md` (new)
- `CONTRIBUTING.md` (new)

### Deviations from the plan
- Animated GIF / asciinema demo: skipped, see above.
- The flag reference is a curated highlights list rather than an
  auto-generated table; users running `pgtail --help` get the authoritative
  one anyway, and we don't want two reference docs to keep in sync.
