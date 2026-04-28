"""Optional TOML config file support.

Lookup order when no explicit path is given:
    1. ./.pgtail.toml (current working directory)
    2. ~/.config/pgtail/config.toml

Schema (all keys optional):
    [default]
    schema = ["public"]
    tables = ["users", "orders"]
    exclude = ["audit_*"]
    ops = ["insert", "update", "delete"]
    json = false
    no_color = false
    no_time = false
    verbose = false
    max_width = 80
    redact = ["password", "token"]
    slot = "my_slot"
    log_file = "/tmp/pgtail.log"
    expand_all = false
    collapse_threshold = 1000
    dsn = "postgresql://..."

Precedence (handled in cli.py): CLI flag > env var > config file > built-in default.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Raised when a config file is present but malformed."""


def candidate_paths() -> list[Path]:
    return [
        Path.cwd() / ".pgtail.toml",
        Path.home() / ".config" / "pgtail" / "config.toml",
    ]


def find_config(explicit: Path | None = None) -> Path | None:
    """Return the first existing config path, or None."""
    if explicit is not None:
        return explicit if explicit.exists() else None
    for p in candidate_paths():
        if p.exists():
            return p
    return None


def load_config(explicit: Path | None = None) -> dict[str, Any]:
    """Return the [default] section of the resolved config file (or {})."""
    path = find_config(explicit)
    if path is None:
        if explicit is not None:
            raise ConfigError(f"config file not found: {explicit}")
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"could not read config file {path}: {e}") from e

    section = data.get("default", {})
    if not isinstance(section, dict):
        raise ConfigError(f"config {path}: [default] section must be a table")
    return _normalize(section)


def _normalize(section: dict[str, Any]) -> dict[str, Any]:
    """Convert TOML-friendly types to the strings the CLI parsers expect.

    Lists become comma-joined strings (matching the CLI's CSV format) so the
    callback can run them through ``parse_csv_tuple`` / ``parse_ops`` uniformly.
    """
    out: dict[str, Any] = {}
    for key, value in section.items():
        if isinstance(value, list):
            out[key] = ",".join(str(v) for v in value)
        else:
            out[key] = value
    return out


__all__ = ["ConfigError", "candidate_paths", "find_config", "load_config"]
