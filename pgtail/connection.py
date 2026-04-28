"""Connection helpers: validate that the DSN is reachable before streaming."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


class ConnectionError_(Exception):
    """User-facing connection failure."""


@dataclass
class ConnectionInfo:
    server_version: int  # e.g. 160002
    current_database: str
    current_user: str


def validate_connection(dsn: str, *, connect_timeout: int = 5) -> ConnectionInfo:
    """Open a brief connection to confirm the DSN is reachable.

    Raises ConnectionError_ with a friendly message on any failure.
    """
    if not dsn:
        raise ConnectionError_("No DSN provided. Pass one as an argument or set DATABASE_URL.")

    if not (
        dsn.startswith("postgres://")
        or dsn.startswith("postgresql://")
        or "=" in dsn  # keyword/value style: "host=... dbname=..."
    ):
        raise ConnectionError_(
            f"DSN does not look like a Postgres URL: {dsn!r}. "
            "Expected 'postgresql://user:pass@host:port/db' or keyword=value pairs."
        )

    try:
        with (
            psycopg.connect(dsn, connect_timeout=connect_timeout, autocommit=True) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                "SELECT current_setting('server_version_num')::int, "
                "current_database(), current_user"
            )
            row = cur.fetchone()
            assert row is not None
            return ConnectionInfo(
                server_version=int(row[0]),
                current_database=str(row[1]),
                current_user=str(row[2]),
            )
    except psycopg.OperationalError as e:
        raise ConnectionError_(f"Could not connect to Postgres: {e}".strip()) from e
    except Exception as e:  # pragma: no cover — defensive
        raise ConnectionError_(f"Unexpected error connecting to Postgres: {e}") from e
