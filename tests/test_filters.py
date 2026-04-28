"""Tests for filter predicates."""

from __future__ import annotations

from datetime import UTC, datetime

from pgtail.events import ChangeEvent
from pgtail.filters import (
    SYSTEM_SCHEMAS,
    event_allowed,
    op_allowed,
    redact_set,
    schema_allowed,
    table_allowed,
)
from pgtail.options import Settings

TS = datetime(2026, 1, 1, tzinfo=UTC)


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
        redact=("password",),
        slot=None,
        log_file=None,
        expand_all=False,
        collapse_threshold=1000,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ev(table: str = "users", op: str = "insert", schema: str = "public") -> ChangeEvent:
    return ChangeEvent(
        op=op,  # type: ignore[arg-type]
        schema=schema,
        table=table,
        ts=TS,
        new_row={"id": 1},
    )


# --- table glob -------------------------------------------------------------


def test_table_include_exact() -> None:
    s = _settings(tables=("users",))
    assert table_allowed("users", s) is True
    assert table_allowed("orders", s) is False


def test_table_include_glob() -> None:
    s = _settings(tables=("order_*",))
    assert table_allowed("order_items", s) is True
    assert table_allowed("orders", s) is False


def test_table_exclude_glob() -> None:
    s = _settings(exclude=("*_log",))
    assert table_allowed("audit_log", s) is False
    assert table_allowed("event_log", s) is False
    assert table_allowed("users", s) is True


def test_table_exclude_overrides_include() -> None:
    s = _settings(tables=("*",), exclude=("audit_*",))
    assert table_allowed("audit_log", s) is False
    assert table_allowed("users", s) is True


# --- schema -----------------------------------------------------------------


def test_schema_default_public() -> None:
    s = _settings()
    assert schema_allowed("public", s) is True
    assert schema_allowed("app", s) is False  # not in --schema


def test_schema_explicit_list() -> None:
    s = _settings(schemas=("public", "app"))
    assert schema_allowed("app", s) is True
    assert schema_allowed("other", s) is False


def test_system_schemas_hidden_by_default() -> None:
    s = _settings(schemas=("public", "pg_catalog"))
    # If user opts into pg_catalog explicitly we honor it.
    assert schema_allowed("pg_catalog", s) is True

    s_no = _settings(schemas=("public",))
    for sys_schema in SYSTEM_SCHEMAS:
        assert schema_allowed(sys_schema, s_no) is False


# --- ops --------------------------------------------------------------------


def test_op_filtering() -> None:
    s = _settings(ops=("update",))
    assert op_allowed("update", s) is True
    assert op_allowed("insert", s) is False


# --- composite event_allowed -----------------------------------------------


def test_event_allowed_normal() -> None:
    s = _settings(tables=("users",))
    assert event_allowed(_ev(), s) is True
    assert event_allowed(_ev(table="orders"), s) is False


def test_event_allowed_truncate_keeps_if_any_table_matches() -> None:
    s = _settings(tables=("users",))
    ev = ChangeEvent(
        op="truncate",
        schema="public",
        table="users",
        ts=TS,
        truncated_tables=("public.users", "public.orders"),
    )
    assert event_allowed(ev, s) is True

    s2 = _settings(tables=("nope",))
    assert event_allowed(ev, s2) is False


def test_event_allowed_drops_op() -> None:
    s = _settings(ops=("delete",))
    assert event_allowed(_ev(op="insert"), s) is False
    assert event_allowed(_ev(op="delete"), s) is True


# --- redact_set -------------------------------------------------------------


def test_redact_set_lowercases() -> None:
    s = _settings(redact=("Password", "API_KEY"))
    assert redact_set(s) == {"password", "api_key"}
