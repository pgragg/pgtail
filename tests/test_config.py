"""Config-file tests (loading + CLI precedence)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pgtail.cli import app
from pgtail.config import ConfigError, find_config, load_config

runner = CliRunner()


def test_load_no_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert load_config() == {}


def test_load_explicit_path(tmp_path: Path) -> None:
    p = tmp_path / "c.toml"
    p.write_text(
        """
        [default]
        tables = ["users", "orders"]
        max_width = 50
        slot = "foo"
        """,
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg["tables"] == "users,orders"
    assert cfg["max_width"] == 50
    assert cfg["slot"] == "foo"


def test_load_missing_explicit_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.toml")


def test_malformed_toml_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.toml"
    p.write_text("[default\nkey =", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p)


def test_default_section_must_be_table(tmp_path: Path) -> None:
    p = tmp_path / "c.toml"
    p.write_text("default = 5\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p)


def test_find_config_prefers_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pgtail.toml").write_text("[default]\n", encoding="utf-8")
    assert find_config() == tmp_path / ".pgtail.toml"


# --- CLI precedence ---------------------------------------------------------


def test_cli_overrides_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A CLI flag should beat the config file for the same option."""
    cfg = tmp_path / "c.toml"
    cfg.write_text('[default]\ntables = ["from_config"]\nmax_width = 7\n', encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_validate(dsn: str, *, connect_timeout: int = 5):
        from pgtail.connection import ConnectionInfo

        return ConnectionInfo(server_version=170000, current_database="x", current_user="y")

    def fake_preflight(dsn: str, *, connect_timeout: int = 5):
        return None

    def fake_stream(settings):
        captured["settings"] = settings
        return iter([])

    monkeypatch.setattr("pgtail.cli.validate_connection", fake_validate)
    monkeypatch.setattr("pgtail.cli.run_preflight", fake_preflight)
    monkeypatch.setattr("pgtail.cli.stream_changes", fake_stream)

    # CLI passes --tables; should win over config.
    result = runner.invoke(
        app,
        [
            "--config",
            str(cfg),
            "--tables",
            "from_cli",
            "postgresql://x@h/db",
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    s = captured["settings"]
    assert s.tables == ("from_cli",)  # CLI wins
    assert s.max_width == 7  # config applies (no CLI override)


def test_config_applies_when_no_cli_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text('[default]\ntables = ["users", "orders"]\nverbose = true\n', encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_validate(dsn, *, connect_timeout=5):
        from pgtail.connection import ConnectionInfo

        return ConnectionInfo(server_version=170000, current_database="x", current_user="y")

    monkeypatch.setattr("pgtail.cli.validate_connection", fake_validate)
    monkeypatch.setattr("pgtail.cli.run_preflight", lambda *a, **kw: None)

    def fake_stream(settings):
        captured["settings"] = settings
        return iter([])

    monkeypatch.setattr("pgtail.cli.stream_changes", fake_stream)

    result = runner.invoke(app, ["--config", str(cfg), "postgresql://x@h/db"])
    assert result.exit_code == 0, result.stderr or result.stdout
    s = captured["settings"]
    assert s.tables == ("users", "orders")
    assert s.verbose is True
