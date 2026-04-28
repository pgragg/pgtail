"""Unit tests for preflight helpers (no live DB required)."""

from __future__ import annotations

from pgtail.preflight import (
    _format_replication_role_fix,
    _format_wal_level_fix,
    _hostname_from_dsn,
    detect_provider,
)


def test_hostname_from_url() -> None:
    assert _hostname_from_dsn("postgresql://u:p@db.example.com:5432/x") == "db.example.com"


def test_hostname_from_keyword_form() -> None:
    assert _hostname_from_dsn("host=db.example.com port=5432 dbname=x user=u") == "db.example.com"


def test_hostname_missing() -> None:
    assert _hostname_from_dsn("") is None


def test_detect_provider_rds() -> None:
    p = detect_provider("mydb.cluster-abc123.us-east-1.rds.amazonaws.com")
    assert p is not None
    assert "AWS" in p[0]


def test_detect_provider_supabase() -> None:
    p = detect_provider("db.abcd.supabase.co")
    assert p is not None
    assert p[0] == "Supabase"


def test_detect_provider_neon() -> None:
    p = detect_provider("ep-foo.us-east-2.aws.neon.tech")
    assert p is not None
    assert p[0] == "Neon"


def test_detect_provider_unknown() -> None:
    assert detect_provider("localhost") is None
    assert detect_provider(None) is None


def test_wal_level_fix_text_mentions_logical() -> None:
    msg = _format_wal_level_fix("replica")
    assert "logical" in msg
    assert "ALTER SYSTEM" in msg


def test_replication_role_fix_text_mentions_user() -> None:
    msg = _format_replication_role_fix("alice")
    assert "alice" in msg
    assert "REPLICATION" in msg
