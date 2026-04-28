"""Tests for CLI argument parsing and option resolution (ticket 002)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from pgtail.cli import app
from pgtail.options import DEFAULT_OPS, DEFAULT_REDACT, Settings, parse_csv_tuple, parse_ops

runner = CliRunner()


def test_help_lists_every_flag() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout
    for flag in [
        "--schema",
        "--tables",
        "--exclude",
        "--ops",
        "--json",
        "--no-color",
        "--no-time",
        "--verbose",
        "--max-width",
        "--redact",
        "--slot",
        "--log-file",
        "--expand-all",
        "--collapse-threshold",
        "--version",
    ]:
        assert flag in out, f"missing {flag} in --help"


def test_missing_dsn_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "no DSN" in result.stderr or "no DSN" in result.stdout


def test_bad_dsn_string_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = runner.invoke(app, ["not-a-real-url"])
    assert result.exit_code == 2


def test_unreachable_dsn_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Port 1 is reserved/unused; connect will fail fast.
    result = runner.invoke(
        app,
        ["postgresql://nope:nope@127.0.0.1:1/none"],
    )
    assert result.exit_code == 2


def test_invalid_ops_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = runner.invoke(
        app,
        ["postgresql://x@127.0.0.1:1/db", "--ops", "insert,bogus"],
    )
    assert result.exit_code == 2


def test_parse_ops_default() -> None:
    assert parse_ops(",".join(DEFAULT_OPS)) == DEFAULT_OPS


def test_parse_ops_normalizes_case() -> None:
    assert parse_ops("INSERT,Update") == ("insert", "update")


def test_parse_ops_invalid() -> None:
    with pytest.raises(ValueError):
        parse_ops("insert,frobnicate")


def test_parse_csv_tuple_handles_empty() -> None:
    assert parse_csv_tuple(None) == ()
    assert parse_csv_tuple("") == ()
    assert parse_csv_tuple(" a , b ,, c ") == ("a", "b", "c")


def test_settings_dsn_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://envhost/db")
    assert Settings.resolve_dsn(None) == "postgresql://envhost/db"
    assert Settings.resolve_dsn("postgresql://override/db") == "postgresql://override/db"


def test_settings_dsn_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings.resolve_dsn(None) is None


def test_settings_no_color_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert Settings.resolve_color(no_color_flag=False) is False
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert Settings.resolve_color(no_color_flag=False) is True
    assert Settings.resolve_color(no_color_flag=True) is False


def test_default_redact_constant() -> None:
    assert "password" in DEFAULT_REDACT
    assert "token" in DEFAULT_REDACT
