"""Preflight checks: wal_level + REPLICATION role attribute, with friendly fix-up text."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import psycopg


class PreflightError(Exception):
    """A preflight check failed. The message is intended for end-user display."""


@dataclass(frozen=True)
class PreflightInfo:
    wal_level: str
    has_replication: bool
    current_user: str
    host: str | None


# Hostname substrings → managed-provider doc URLs.
_PROVIDER_HINTS: tuple[tuple[str, str, str], ...] = (
    (
        "rds.amazonaws.com",
        "AWS RDS / Aurora",
        "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html"
        "#PostgreSQL.Concepts.General.FeatureSupport.LogicalReplication",
    ),
    (
        "supabase.co",
        "Supabase",
        "https://supabase.com/docs/guides/database/replication",
    ),
    (
        "supabase.com",
        "Supabase",
        "https://supabase.com/docs/guides/database/replication",
    ),
    (
        "neon.tech",
        "Neon",
        "https://neon.tech/docs/guides/logical-replication-postgres",
    ),
    (
        "cloud.google.com",
        "Google Cloud SQL",
        "https://cloud.google.com/sql/docs/postgres/replication/configure-logical-replication",
    ),
    (
        "azure.com",
        "Azure Database for PostgreSQL",
        "https://learn.microsoft.com/azure/postgresql/flexible-server/concepts-logical",
    ),
    (
        "render.com",
        "Render",
        "https://render.com/docs/postgresql-creating-connecting",
    ),
    (
        "railway.app",
        "Railway",
        "https://docs.railway.app/databases/postgresql",
    ),
)


def _hostname_from_dsn(dsn: str) -> str | None:
    if not dsn:
        return None
    try:
        # urlparse handles postgresql://... ; for keyword form fall back to None.
        if "://" in dsn:
            parsed = urlparse(dsn)
            return parsed.hostname
        # keyword=value form
        for chunk in dsn.split():
            if chunk.startswith("host="):
                return chunk.split("=", 1)[1]
    except Exception:  # pragma: no cover — defensive
        return None
    return None


def detect_provider(hostname: str | None) -> tuple[str, str] | None:
    """Return (provider_name, docs_url) if the hostname matches a known provider."""
    if not hostname:
        return None
    host_low = hostname.lower()
    for needle, name, url in _PROVIDER_HINTS:
        if needle in host_low:
            return (name, url)
    return None


def run_preflight(dsn: str, *, connect_timeout: int = 5) -> PreflightInfo:
    """Connect briefly and verify wal_level=logical and REPLICATION attribute.

    Raises PreflightError with a human-readable, copy-pasteable fix on failure.
    """
    host = _hostname_from_dsn(dsn)

    try:
        with (
            psycopg.connect(dsn, connect_timeout=connect_timeout, autocommit=True) as conn,
            conn.cursor() as cur,
        ):
            cur.execute("SHOW wal_level")
            row = cur.fetchone()
            assert row is not None
            wal_level = str(row[0])

            cur.execute("SELECT rolname, rolreplication FROM pg_roles WHERE rolname = current_user")
            r = cur.fetchone()
            assert r is not None
            current_user = str(r[0])
            has_replication = bool(r[1])
    except psycopg.OperationalError as e:
        # Connection-level errors are handled by validate_connection in ticket 002,
        # but if preflight is called standalone we surface them here too.
        raise PreflightError(f"could not connect to Postgres for preflight: {e}".strip()) from e

    info = PreflightInfo(
        wal_level=wal_level,
        has_replication=has_replication,
        current_user=current_user,
        host=host,
    )

    problems: list[str] = []
    if wal_level != "logical":
        problems.append(_format_wal_level_fix(wal_level))
    if not has_replication:
        problems.append(_format_replication_role_fix(current_user))

    if problems:
        provider = detect_provider(host)
        msg = "\n\n".join(problems)
        if provider:
            name, url = provider
            msg += (
                f"\n\nDetected managed provider: {name}. "
                f"Some settings can only be changed via the provider console.\n"
                f"See: {url}"
            )
        raise PreflightError(msg)

    return info


def _format_wal_level_fix(current: str) -> str:
    return (
        f"wal_level is '{current}' but pgtail needs 'logical'.\n"
        "Fix (requires a Postgres restart):\n"
        "    ALTER SYSTEM SET wal_level = 'logical';\n"
        "    -- then restart the Postgres server\n"
        "On managed providers this is usually a parameter group / dashboard setting "
        "(see provider link below)."
    )


def _format_replication_role_fix(user: str) -> str:
    return (
        f"role '{user}' is missing the REPLICATION attribute.\n"
        "Fix (run as a superuser):\n"
        f"    ALTER ROLE {user} WITH REPLICATION;\n"
        "Or create a dedicated replication user:\n"
        "    CREATE ROLE pgtail_reader WITH LOGIN REPLICATION PASSWORD '...';"
    )
