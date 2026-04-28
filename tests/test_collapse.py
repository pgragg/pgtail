"""Tests for the large-transaction collapser."""

from __future__ import annotations

from datetime import UTC, datetime

from pgtail.collapse import Collapser
from pgtail.events import ChangeEvent
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
        redact=(),
        slot=None,
        log_file=None,
        expand_all=False,
        collapse_threshold=3,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ev(*, txid: int = 1, table: str = "users", op: str = "update") -> ChangeEvent:
    return ChangeEvent(
        op=op,  # type: ignore[arg-type]
        schema="public",
        table=table,
        ts=TS,
        txid=txid,
        new_row={"id": 1},
    )


def test_below_threshold_passes_through() -> None:
    c = Collapser(_settings(collapse_threshold=5))
    out: list[ChangeEvent] = []
    for _ in range(3):
        out.extend(c.process(_ev()))
    out.extend(c.flush())
    assert len(out) == 3
    assert all(not e.extra for e in out)


def test_threshold_collapses_remaining() -> None:
    c = Collapser(_settings(collapse_threshold=3))
    out: list[ChangeEvent] = []
    for _ in range(10):
        out.extend(c.process(_ev()))
    out.extend(c.flush())
    # Expect: 3 raw + 1 notice + 1 summary = 5
    notices = [e for e in out if e.extra.get("collapse_notice")]
    summaries = [e for e in out if e.extra.get("collapsed_count")]
    assert len(notices) == 1
    assert len(summaries) == 1
    assert summaries[0].extra["collapsed_count"] == 10
    raw = [e for e in out if not e.extra]
    assert len(raw) == 3


def test_expand_all_bypasses() -> None:
    c = Collapser(_settings(collapse_threshold=2, expand_all=True))
    out: list[ChangeEvent] = []
    for _ in range(10):
        out.extend(c.process(_ev()))
    out.extend(c.flush())
    assert len(out) == 10
    assert all(not e.extra for e in out)


def test_independent_groups_per_table_and_op() -> None:
    c = Collapser(_settings(collapse_threshold=2))
    out: list[ChangeEvent] = []
    for _ in range(5):
        out.extend(c.process(_ev(table="users", op="update")))
    for _ in range(5):
        out.extend(c.process(_ev(table="orders", op="update")))
    out.extend(c.flush())
    summaries = [e for e in out if e.extra.get("collapsed_count")]
    assert {s.table for s in summaries} == {"users", "orders"}


def test_txid_change_flushes_previous() -> None:
    c = Collapser(_settings(collapse_threshold=2))
    out: list[ChangeEvent] = []
    for _ in range(5):
        out.extend(c.process(_ev(txid=1)))
    # New txid should trigger summary for txid=1.
    out.extend(c.process(_ev(txid=2)))
    summaries = [e for e in out if e.extra.get("collapsed_count")]
    assert len(summaries) == 1
    assert summaries[0].txid == 1


def test_truncate_never_collapsed() -> None:
    c = Collapser(_settings(collapse_threshold=1))
    out: list[ChangeEvent] = []
    for _ in range(5):
        out.extend(
            c.process(
                ChangeEvent(
                    op="truncate",
                    schema="public",
                    table="users",
                    ts=TS,
                    txid=1,
                    truncated_tables=("public.users",),
                )
            )
        )
    out.extend(c.flush())
    assert len(out) == 5
    assert all(e.op == "truncate" and not e.extra for e in out)
