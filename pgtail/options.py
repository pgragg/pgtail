"""Runtime options shared across the CLI, replication, and formatter layers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_REDACT: tuple[str, ...] = (
    "password",
    "password_hash",
    "api_key",
    "secret",
    "token",
)
DEFAULT_OPS: tuple[str, ...] = ("insert", "update", "delete")
VALID_OPS: frozenset[str] = frozenset({"insert", "update", "delete", "truncate"})


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    """All runtime options resolved from CLI / env / defaults."""

    dsn: str

    # Filtering
    schemas: tuple[str, ...] = ("public",)
    tables: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    ops: tuple[str, ...] = DEFAULT_OPS

    # Output
    json_output: bool = False
    color: bool = True
    show_time: bool = True
    verbose: bool = False
    max_width: int = 80

    # Redaction
    redact: tuple[str, ...] = DEFAULT_REDACT

    # Replication slot
    slot: str | None = None  # None => ephemeral

    # Tee
    log_file: Path | None = None

    # Large-txn collapsing (ticket 007)
    expand_all: bool = False
    collapse_threshold: int = 1000

    # Computed
    extra: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def resolve_dsn(cli_dsn: str | None) -> str | None:
        """Pick the DSN: CLI arg wins, then DATABASE_URL env var."""
        if cli_dsn:
            return cli_dsn
        env = os.environ.get("DATABASE_URL")
        return env or None

    @staticmethod
    def resolve_color(no_color_flag: bool) -> bool:
        """Honor --no-color and NO_COLOR env var (https://no-color.org)."""
        if no_color_flag:
            return False
        return not os.environ.get("NO_COLOR")


def parse_ops(raw: str) -> tuple[str, ...]:
    """Parse a comma-separated --ops value, validating each entry."""
    parts = _split_csv(raw)
    if not parts:
        return DEFAULT_OPS
    bad = [p for p in parts if p.lower() not in VALID_OPS]
    if bad:
        raise ValueError(f"Unknown op(s): {', '.join(bad)}. Valid: {', '.join(sorted(VALID_OPS))}")
    return tuple(p.lower() for p in parts)


def parse_csv_tuple(raw: str | None) -> tuple[str, ...]:
    return tuple(_split_csv(raw))
