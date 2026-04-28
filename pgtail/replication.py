"""Logical replication stream: set up publication + slot, decode pgoutput, yield ChangeEvents.

Architecture
------------
1.  Open a regular psycopg connection to create the publication (and, when
    ephemeral, the temp slot via ``pg_create_logical_replication_slot``).
2.  Open a *replication* connection (``replication=database`` connection
    parameter) and issue ``START_REPLICATION SLOT name LOGICAL 0/0
    (proto_version '1', publication_names 'pub')``.
3.  Read the resulting COPY stream. Each row is one replication-protocol
    message: ``XLogData`` (``w``) carries a pgoutput payload; ``Keepalive``
    (``k``) prompts a status update.
4.  Decode pgoutput payloads via :mod:`pgtail.pgoutput`, maintain a relation
    cache, and yield :class:`pgtail.events.ChangeEvent` objects.
5.  On exit, drop the publication (and the slot if it was ephemeral).

We support psycopg 3 only. The replication connection is created with
``autocommit=True`` and ``prepare_threshold=None`` so we can issue
non-prepared replication commands.
"""

from __future__ import annotations

import logging
import secrets
import select
import struct
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg import pq

from pgtail.events import ChangeEvent
from pgtail.options import Settings
from pgtail.pgoutput import (
    BeginMsg,
    CommitMsg,
    DeleteMsg,
    InsertMsg,
    OriginMsg,
    RelationMsg,
    TruncateMsg,
    TypeMsg,
    UpdateMsg,
    decode_message,
    is_unchanged,
    tuple_to_dict,
)

log = logging.getLogger(__name__)

_PG_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


def _now_pg_micros() -> int:
    return int((datetime.now(tz=UTC) - _PG_EPOCH).total_seconds() * 1_000_000)


def _lsn_to_str(lsn_int: int) -> str:
    return f"{lsn_int >> 32:X}/{lsn_int & 0xFFFFFFFF:X}"


# ---------------------------------------------------------------------------
# Publication / slot setup
# ---------------------------------------------------------------------------


@contextmanager
def _setup_publication_and_slot(
    settings: Settings,
) -> Iterator[tuple[str, str, bool]]:
    """Create (and on exit clean up) the publication and replication slot.

    Yields (publication_name, slot_name, slot_is_temp).
    """
    suffix = secrets.token_hex(4)
    pub_name = f"pgtail_pub_{suffix}"
    slot_name = settings.slot or f"pgtail_{suffix}"
    slot_is_temp = settings.slot is None

    # Build CREATE PUBLICATION statement. If the user gave explicit tables we
    # try to attach them; if any are missing we fall back to FOR ALL TABLES so
    # that pgtail still works (filtering happens client-side in ticket 006).
    qualified_tables: list[str] = []
    if settings.tables:
        try:
            qualified_tables = _resolve_tables(settings)
        except Exception as exc:  # pragma: no cover — defensive
            log.warning("could not resolve tables, falling back to FOR ALL TABLES: %s", exc)
            qualified_tables = []

    with psycopg.connect(settings.dsn, autocommit=True) as conn, conn.cursor() as cur:
        if qualified_tables:
            tables_sql = ", ".join(qualified_tables)
            cur.execute(f"CREATE PUBLICATION {pub_name} FOR TABLE {tables_sql}")
        else:
            cur.execute(f"CREATE PUBLICATION {pub_name} FOR ALL TABLES")

        slot_existed = False
        if not slot_is_temp:
            cur.execute(
                "SELECT 1 FROM pg_replication_slots WHERE slot_name = %s",
                (slot_name,),
            )
            slot_existed = cur.fetchone() is not None

        if not slot_existed:
            # We always create a permanent slot at the SQL level. "Temporary" slots
            # in Postgres are tied to the session that created them, so they would
            # vanish before the replication connection opens. We track temp/persistent
            # ourselves and drop the slot on exit when ephemeral.
            cur.execute(
                "SELECT pg_create_logical_replication_slot(%s, 'pgoutput', false)",
                (slot_name,),
            )

    try:
        yield pub_name, slot_name, slot_is_temp
    finally:
        # Drop publication always; drop slot only when we created it ephemerally.
        try:
            with (
                psycopg.connect(settings.dsn, autocommit=True) as conn,
                conn.cursor() as cur,
            ):
                cur.execute(f"DROP PUBLICATION IF EXISTS {pub_name}")
                if slot_is_temp:
                    cur.execute(
                        "SELECT pg_drop_replication_slot(%s) "
                        "WHERE EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = %s)",
                        (slot_name, slot_name),
                    )
        except Exception as exc:  # pragma: no cover — best-effort cleanup
            log.warning("cleanup error (publication=%s slot=%s): %s", pub_name, slot_name, exc)


def _resolve_tables(settings: Settings) -> list[str]:
    """Resolve glob-style table includes against pg_class. Returns qualified names."""
    import fnmatch

    schemas = settings.schemas or ("public",)
    with (
        psycopg.connect(settings.dsn, autocommit=True) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(
            """
            SELECT n.nspname, c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname = ANY(%s)
            """,
            (list(schemas),),
        )
        rows = cur.fetchall()

    matched: list[str] = []
    for ns, rel in rows:
        for pat in settings.tables:
            if fnmatch.fnmatchcase(rel, pat):
                matched.append(f'"{ns}"."{rel}"')
                break
    return matched


# ---------------------------------------------------------------------------
# Replication protocol framing
# ---------------------------------------------------------------------------
#
# The COPY stream from START_REPLICATION returns rows whose first byte is a
# message type:
#   'w' XLogData: starting WAL pos (8) | current end WAL (8) | server time (8)
#                 | payload bytes
#   'k' Primary keepalive: end WAL (8) | server time (8) | reply requested (1)
#
# We reply with Standby Status Update messages (type 'r') containing four
# 8-byte LSNs (last received, last flushed, last applied) plus an 8-byte
# timestamp and a 1-byte "request reply" flag.


def _build_status_update(last_lsn: int, *, request_reply: bool = False) -> bytes:
    return (
        b"r"
        + struct.pack(">QQQQ", last_lsn, last_lsn, last_lsn, _now_pg_micros())
        + (b"\x01" if request_reply else b"\x00")
    )


def _parse_xlog_or_keepalive(row: bytes) -> tuple[str, dict[str, Any]]:
    """Return (kind, fields)."""
    if not row:
        raise ValueError("replication: empty row")
    kind = chr(row[0])
    if kind == "w":
        wal_start, wal_end, server_ts = struct.unpack(">QQQ", row[1:25])
        payload = row[25:]
        return "w", {
            "wal_start": wal_start,
            "wal_end": wal_end,
            "server_ts": server_ts,
            "payload": payload,
        }
    if kind == "k":
        wal_end, server_ts, reply = struct.unpack(">QQB", row[1:18])
        return "k", {"wal_end": wal_end, "server_ts": server_ts, "reply_requested": bool(reply)}
    raise ValueError(f"replication: unknown row kind {kind!r}")


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


def stream_changes(settings: Settings) -> Iterator[ChangeEvent]:
    """Generator that yields ChangeEvents until the caller stops iterating
    or the connection is closed.

    On normal generator close (e.g. ``break`` in the consumer or KeyboardInterrupt
    raised in the consumer's frame), the publication/slot cleanup runs.
    """
    with _setup_publication_and_slot(settings) as (pub_name, slot_name, _is_temp):
        # Open replication connection.
        # psycopg accepts replication=database via connection params.
        repl_dsn = settings.dsn
        with psycopg.Connection.connect(
            repl_dsn,
            autocommit=True,
            prepare_threshold=None,
            replication="database",
        ) as repl_conn:
            yield from _stream_loop(repl_conn, pub_name, slot_name)


def _stream_loop(
    repl_conn: psycopg.Connection[Any], pub_name: str, slot_name: str
) -> Iterator[ChangeEvent]:
    """Drive START_REPLICATION via the low-level pgconn (libpq) API.

    psycopg3 does not yet support COPY_BOTH at the cursor level, so we send
    queries and read copy data directly. Status updates are written back via
    ``put_copy_data``.
    """
    pgconn = repl_conn.pgconn
    start_sql = (
        f"START_REPLICATION SLOT {slot_name} LOGICAL 0/0 ("
        f"proto_version '1', publication_names '{pub_name}')"
    ).encode()
    pgconn.send_query(start_sql)
    result = pgconn.get_result()
    if result is None:
        raise RuntimeError("replication: no result from START_REPLICATION")
    if result.status != pq.ExecStatus.COPY_BOTH:
        err = (result.error_message or b"").decode(errors="replace")
        raise RuntimeError(f"replication: expected COPY_BOTH, got status={result.status} ({err})")

    relations: dict[int, RelationMsg] = {}
    current_txid: int | None = None
    last_received_lsn = 0
    last_keepalive = datetime.now(tz=UTC)

    def send_status(lsn: int, *, request_reply: bool = False) -> None:
        pgconn.put_copy_data(_build_status_update(lsn, request_reply=request_reply))
        pgconn.flush()

    try:
        while True:
            # Drain any pending bytes; non-blocking.
            pgconn.consume_input()
            # psycopg3 returns (nbytes, memoryview):
            #   nbytes > 0  -> message available
            #   nbytes == 0 -> no data yet (async would-block)
            #   nbytes == -1 -> end of COPY stream
            #   nbytes == -2 -> error
            nbytes, view = pgconn.get_copy_data(1)
            if nbytes == -1:
                break
            if nbytes == -2:
                err = (pgconn.error_message or b"").decode(errors="replace")
                raise RuntimeError(f"replication: get_copy_data error: {err}")
            if nbytes == 0:
                # Would block. Wait briefly for more data and continue.
                fd = pgconn.socket
                select.select([fd], [], [], 1.0)
                # Heartbeat keepalive every ~10s.
                now = datetime.now(tz=UTC)
                if now - last_keepalive > timedelta(seconds=10):
                    send_status(last_received_lsn)
                    last_keepalive = now
                continue

            data = bytes(view)
            try:
                kind, fields = _parse_xlog_or_keepalive(data)
            except ValueError as exc:
                log.warning("skipping malformed replication row: %s", exc)
                continue

            if kind == "k":
                last_received_lsn = max(last_received_lsn, fields["wal_end"])
                if fields["reply_requested"]:
                    send_status(last_received_lsn)
                continue

            wal_start: int = fields["wal_start"]
            wal_end: int = fields["wal_end"]
            payload: bytes = fields["payload"]
            last_received_lsn = max(last_received_lsn, wal_end, wal_start)

            try:
                msg = decode_message(payload)
            except ValueError as exc:
                log.warning("skipping undecodable pgoutput message: %s", exc)
                continue

            if isinstance(msg, BeginMsg):
                current_txid = msg.xid
                continue
            if isinstance(msg, CommitMsg):
                current_txid = None
                send_status(msg.end_lsn)
                continue
            if isinstance(msg, OriginMsg | TypeMsg):
                continue
            if isinstance(msg, RelationMsg):
                relations[msg.oid] = msg
                continue

            now = datetime.now(tz=UTC)
            if now - last_keepalive > timedelta(seconds=10):
                send_status(last_received_lsn)
                last_keepalive = now

            event = _msg_to_event(msg, relations, current_txid, wal_start)
            if event is not None:
                yield event
    finally:
        # Best-effort: tell the server we're done, then drain any trailing results.
        try:
            pgconn.put_copy_end()
            pgconn.flush()
            while pgconn.get_result() is not None:
                pass
        except Exception as exc:  # pragma: no cover
            log.debug("copy-end ignored: %s", exc)


def _msg_to_event(
    msg: object,
    relations: dict[int, RelationMsg],
    txid: int | None,
    lsn: int,
) -> ChangeEvent | None:
    ts = datetime.now(tz=UTC)

    if isinstance(msg, InsertMsg):
        rel = relations.get(msg.relation_oid)
        if rel is None:
            return None
        return ChangeEvent(
            op="insert",
            schema=rel.namespace,
            table=rel.name,
            ts=ts,
            txid=txid,
            lsn=_lsn_to_str(lsn),
            new_row=tuple_to_dict(msg.new_tuple, rel.columns),
        )
    if isinstance(msg, DeleteMsg):
        rel = relations.get(msg.relation_oid)
        if rel is None:
            return None
        return ChangeEvent(
            op="delete",
            schema=rel.namespace,
            table=rel.name,
            ts=ts,
            txid=txid,
            lsn=_lsn_to_str(lsn),
            old_row=tuple_to_dict(msg.old_tuple, rel.columns),
        )
    if isinstance(msg, UpdateMsg):
        rel = relations.get(msg.relation_oid)
        if rel is None:
            return None
        new_row = tuple_to_dict(msg.new_tuple, rel.columns)
        old_row: dict[str, Any] | None = None
        changed: tuple[str, ...] = ()
        if msg.old_tuple is not None:
            old_row = tuple_to_dict(msg.old_tuple, rel.columns)
            changed = tuple(
                k
                for k in new_row
                if not is_unchanged(new_row[k]) and (k not in old_row or old_row[k] != new_row[k])
            )
        else:
            # No old tuple sent: every non-unchanged column is potentially the diff.
            changed = tuple(k for k, v in new_row.items() if not is_unchanged(v))
        return ChangeEvent(
            op="update",
            schema=rel.namespace,
            table=rel.name,
            ts=ts,
            txid=txid,
            lsn=_lsn_to_str(lsn),
            new_row=new_row,
            old_row=old_row,
            changed_fields=changed,
        )
    if isinstance(msg, TruncateMsg):
        names = tuple(
            f"{relations[oid].namespace}.{relations[oid].name}"
            for oid in msg.relation_oids
            if oid in relations
        )
        # Use the first table for schema/table fields so the formatter has something.
        first = names[0].split(".") if names else ("", "")
        return ChangeEvent(
            op="truncate",
            schema=first[0],
            table=first[1],
            ts=ts,
            txid=txid,
            lsn=_lsn_to_str(lsn),
            truncated_tables=names,
        )
    return None


# Re-export ``select`` so test stubs can monkeypatch it cleanly.
def drop_slot(dsn: str, slot_name: str) -> bool:
    """Drop a logical replication slot by name. Returns True if it existed."""
    with (
        psycopg.connect(dsn, autocommit=True) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("SELECT 1 FROM pg_replication_slots WHERE slot_name = %s", (slot_name,))
        existed = cur.fetchone() is not None
        if existed:
            cur.execute("SELECT pg_drop_replication_slot(%s)", (slot_name,))
        return existed


__all__ = [
    "_build_status_update",
    "_parse_xlog_or_keepalive",
    "drop_slot",
    "select",
    "stream_changes",
]
