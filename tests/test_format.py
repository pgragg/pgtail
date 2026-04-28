"""Tests for the formatter / renderer."""

from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime

import pytest

from pgtail.events import ChangeEvent
from pgtail.format import Renderer, _strip_ansi
from pgtail.options import Settings

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _settings(**overrides: object) -> Settings:
    base = dict(
        dsn="postgresql://x@localhost/db",
        schemas=("public",),
        tables=(),
        exclude=(),
        ops=("insert", "update", "delete", "truncate"),
        json_output=False,
        color=False,
        show_time=False,
        verbose=False,
        max_width=80,
        redact=("password", "token"),
        slot=None,
        log_file=None,
        expand_all=False,
        collapse_threshold=1000,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _renderer(settings: Settings, buf: io.StringIO | None = None) -> tuple[Renderer, io.StringIO]:
    if buf is None:
        buf = io.StringIO()
    r = Renderer.from_settings(settings, stdout=buf)
    return r, buf


TS = datetime(2026, 1, 1, 10, 42, 1, tzinfo=UTC)


def test_insert_text_render() -> None:
    s = _settings()
    r, buf = _renderer(s)
    r.emit(
        ChangeEvent(
            op="insert",
            schema="public",
            table="users",
            ts=TS,
            new_row={"id": 7, "email": "a@b.com"},
        )
    )
    out = buf.getvalue()
    assert "INSERT" in out
    assert "public.users" in out
    assert "id: 7" in out
    assert '"a@b.com"' in out


def test_delete_text_render() -> None:
    s = _settings()
    r, buf = _renderer(s)
    r.emit(
        ChangeEvent(
            op="delete",
            schema="public",
            table="users",
            ts=TS,
            old_row={"id": 7, "email": "a@b.com"},
        )
    )
    out = buf.getvalue()
    assert "DELETE" in out
    assert "id: 7" in out


def test_update_diff_only_changed() -> None:
    s = _settings()
    r, buf = _renderer(s)
    r.emit(
        ChangeEvent(
            op="update",
            schema="public",
            table="users",
            ts=TS,
            old_row={"id": 7, "email": "a@b.com", "name": "Ana"},
            new_row={"id": 7, "email": "ana@b.com", "name": "Ana"},
            changed_fields=("email",),
        )
    )
    out = buf.getvalue()
    assert "UPDATE" in out
    assert "id=7" in out
    assert 'email: "a@b.com" → "ana@b.com"' in out
    assert "name" not in out  # only changed fields


def test_truncate_render() -> None:
    s = _settings()
    r, buf = _renderer(s)
    r.emit(
        ChangeEvent(
            op="truncate",
            schema="public",
            table="users",
            ts=TS,
            truncated_tables=("public.users", "public.orders"),
        )
    )
    out = buf.getvalue()
    assert "TRUNCATE" in out
    assert "public.users" in out
    assert "public.orders" in out


def test_redaction_in_text() -> None:
    s = _settings(redact=("password",))
    r, buf = _renderer(s)
    r.emit(
        ChangeEvent(
            op="insert",
            schema="public",
            table="users",
            ts=TS,
            new_row={"id": 1, "password": "hunter2"},
        )
    )
    out = buf.getvalue()
    assert "password: ***" in out
    assert "hunter2" not in out


def test_max_width_truncates_value() -> None:
    s = _settings(max_width=10)
    r, buf = _renderer(s)
    r.emit(
        ChangeEvent(
            op="insert",
            schema="public",
            table="logs",
            ts=TS,
            new_row={"id": 1, "msg": "x" * 50},
        )
    )
    out = buf.getvalue()
    assert "…" in out


def test_timestamp_toggle() -> None:
    s_on = _settings(show_time=True)
    r, buf = _renderer(s_on)
    r.emit(ChangeEvent(op="insert", schema="public", table="t", ts=TS, new_row={"id": 1}))
    # local-time conversion may differ, but format is HH:MM:SS
    assert re.search(r"\b\d{2}:\d{2}:\d{2}\b", buf.getvalue())

    s_off = _settings(show_time=False)
    r2, buf2 = _renderer(s_off)
    r2.emit(ChangeEvent(op="insert", schema="public", table="t", ts=TS, new_row={"id": 1}))
    assert not re.search(r"\b\d{2}:\d{2}:\d{2}\b", buf2.getvalue())


def test_verbose_adds_txid_and_lsn() -> None:
    s = _settings(verbose=True)
    r, buf = _renderer(s)
    r.emit(
        ChangeEvent(
            op="insert",
            schema="public",
            table="t",
            ts=TS,
            txid=123,
            lsn="0/ABCDEF",
            new_row={"id": 1},
        )
    )
    out = buf.getvalue()
    assert "txid=123" in out
    assert "lsn=0/ABCDEF" in out


def test_no_color_when_disabled() -> None:
    s = _settings(color=False)
    r, buf = _renderer(s)
    r.emit(ChangeEvent(op="insert", schema="public", table="t", ts=TS, new_row={"id": 1}))
    assert ANSI_RE.search(buf.getvalue()) is None


def test_json_output_is_parseable() -> None:
    s = _settings(json_output=True, verbose=True)
    r, buf = _renderer(s)
    r.emit(
        ChangeEvent(
            op="update",
            schema="public",
            table="users",
            ts=TS,
            txid=42,
            lsn="0/1",
            old_row={"id": 7, "email": "a@b.com", "password": "secret"},
            new_row={"id": 7, "email": "x@b.com", "password": "secret"},
            changed_fields=("email",),
        )
    )
    line = buf.getvalue().strip()
    obj = json.loads(line)
    assert obj["op"] == "update"
    assert obj["schema"] == "public"
    assert obj["table"] == "users"
    assert obj["changed"] == ["email"]
    assert obj["new"]["password"] == "***"
    assert obj["old"]["password"] == "***"
    assert obj["txid"] == 42


def test_log_file_is_plain(tmp_path: pytest.TempPathFactory) -> None:
    log_path = tmp_path / "events.log"  # type: ignore[attr-defined]
    s = _settings(color=True, log_file=log_path)
    r, _ = _renderer(s)
    r.emit(ChangeEvent(op="insert", schema="public", table="t", ts=TS, new_row={"id": 1}))
    r.close()
    content = log_path.read_text()
    assert "INSERT" in content
    assert ANSI_RE.search(content) is None  # no escapes in log file


def test_strip_ansi_helper() -> None:
    s = "\x1b[31mred\x1b[0m and \x1b[1;32mgreen\x1b[0m"
    assert _strip_ansi(s) == "red and green"
