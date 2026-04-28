"""Smoke tests — make sure the package imports and the CLI is wired up."""

from __future__ import annotations

from typer.testing import CliRunner

import pgtail
from pgtail.cli import app


def test_version_string_present() -> None:
    assert isinstance(pgtail.__version__, str)
    assert pgtail.__version__.count(".") >= 1


def test_cli_help_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "pgtail" in result.stdout.lower()


def test_cli_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert pgtail.__version__ in result.stdout
