"""Tests for the --drop-slot CLI flag (mocking the network call)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from pgtail.cli import app

runner = CliRunner()


def test_drop_slot_requires_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = runner.invoke(app, ["--drop-slot", "foo"])
    assert result.exit_code == 2


def test_drop_slot_calls_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_drop(dsn: str, slot_name: str) -> bool:
        called["dsn"] = dsn
        called["slot"] = slot_name
        return True

    # Patch the symbol used by the CLI module.
    monkeypatch.setattr("pgtail.cli.drop_slot", fake_drop)
    result = runner.invoke(app, ["--drop-slot", "myslot", "postgresql://x@h/db"])
    assert result.exit_code == 0
    assert called == {"dsn": "postgresql://x@h/db", "slot": "myslot"}
    assert "dropped replication slot" in result.stdout


def test_drop_slot_missing_slot_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_drop(dsn: str, slot_name: str) -> bool:
        return False

    monkeypatch.setattr("pgtail.cli.drop_slot", fake_drop)
    result = runner.invoke(app, ["--drop-slot", "myslot", "postgresql://x@h/db"])
    assert result.exit_code == 0
    assert "did not exist" in result.stdout
