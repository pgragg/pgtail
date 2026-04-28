"""Unit tests for the pgoutput decoder (pure byte-level parsing)."""

from __future__ import annotations

import struct
from datetime import UTC, datetime

from pgtail.pgoutput import (
    _PG_EPOCH,
    BeginMsg,
    ColumnSpec,
    CommitMsg,
    DeleteMsg,
    InsertMsg,
    RelationMsg,
    TruncateMsg,
    TupleColumn,
    UpdateMsg,
    decode_message,
    decode_value,
    tuple_to_dict,
)

# --- helpers to build pgoutput payloads -------------------------------------


def _cstring(s: str) -> bytes:
    return s.encode("utf-8") + b"\x00"


def _u8(v: int) -> bytes:
    return struct.pack(">B", v)


def _i16(v: int) -> bytes:
    return struct.pack(">h", v)


def _u32(v: int) -> bytes:
    return struct.pack(">I", v)


def _i32(v: int) -> bytes:
    return struct.pack(">i", v)


def _i64(v: int) -> bytes:
    return struct.pack(">q", v)


def _u64(v: int) -> bytes:
    return struct.pack(">Q", v)


def _tuple(cols: list[tuple[str, bytes | None]]) -> bytes:
    """Build a TupleData payload from (kind, data_or_None) pairs."""
    out = _i16(len(cols))
    for kind, data in cols:
        out += kind.encode("ascii")
        if kind in ("n", "u"):
            assert data is None
        else:
            assert data is not None
            out += _u32(len(data)) + data
    return out


# --- decoder tests ----------------------------------------------------------


def test_decode_begin() -> None:
    payload = b"B" + _u64(0xDEADBEEF) + _i64(123_000_000) + _u32(42)
    msg = decode_message(payload)
    assert isinstance(msg, BeginMsg)
    assert msg.final_lsn == 0xDEADBEEF
    assert msg.xid == 42
    assert msg.commit_ts == _PG_EPOCH.replace(tzinfo=UTC) + (
        datetime.fromtimestamp(123, tz=UTC) - datetime.fromtimestamp(0, tz=UTC)
    )


def test_decode_commit() -> None:
    payload = b"C" + _u8(0) + _u64(1) + _u64(2) + _i64(0)
    msg = decode_message(payload)
    assert isinstance(msg, CommitMsg)
    assert msg.commit_lsn == 1
    assert msg.end_lsn == 2


def test_decode_relation_with_columns() -> None:
    payload = (
        b"R"
        + _u32(16384)
        + _cstring("public")
        + _cstring("users")
        + b"d"  # replica identity default
        + _i16(2)
        + _u8(1)
        + _cstring("id")
        + _u32(23)
        + _i32(-1)
        + _u8(0)
        + _cstring("email")
        + _u32(25)
        + _i32(-1)
    )
    msg = decode_message(payload)
    assert isinstance(msg, RelationMsg)
    assert msg.namespace == "public"
    assert msg.name == "users"
    assert msg.replica_identity == "d"
    assert len(msg.columns) == 2
    assert msg.columns[0] == ColumnSpec(flags=1, name="id", type_oid=23, type_mod=-1)
    assert msg.columns[0].is_key is True
    assert msg.columns[1].is_key is False


def test_decode_insert() -> None:
    payload = b"I" + _u32(16384) + b"N" + _tuple([("t", b"7"), ("t", b"a@b.com")])
    msg = decode_message(payload)
    assert isinstance(msg, InsertMsg)
    assert msg.relation_oid == 16384
    assert len(msg.new_tuple) == 2
    assert msg.new_tuple[0] == TupleColumn("t", b"7")


def test_decode_update_with_old_key() -> None:
    payload = (
        b"U"
        + _u32(16384)
        + b"K"
        + _tuple([("t", b"7"), ("n", None)])
        + b"N"
        + _tuple([("t", b"7"), ("t", b"new@b.com")])
    )
    msg = decode_message(payload)
    assert isinstance(msg, UpdateMsg)
    assert msg.old_kind == "K"
    assert msg.old_tuple is not None
    assert msg.new_tuple[1].value == b"new@b.com"


def test_decode_update_no_old() -> None:
    payload = b"U" + _u32(16384) + b"N" + _tuple([("t", b"7"), ("t", b"x")])
    msg = decode_message(payload)
    assert isinstance(msg, UpdateMsg)
    assert msg.old_tuple is None
    assert msg.old_kind is None


def test_decode_delete() -> None:
    payload = b"D" + _u32(16384) + b"K" + _tuple([("t", b"7"), ("n", None)])
    msg = decode_message(payload)
    assert isinstance(msg, DeleteMsg)
    assert msg.old_kind == "K"


def test_decode_truncate() -> None:
    payload = b"T" + _u32(2) + _u8(1) + _u32(16384) + _u32(16385)
    msg = decode_message(payload)
    assert isinstance(msg, TruncateMsg)
    assert msg.flags == 1
    assert msg.relation_oids == (16384, 16385)


def test_decode_unsupported_type() -> None:
    import pytest

    with pytest.raises(ValueError, match="unsupported message type"):
        decode_message(b"Z\x00")


# --- value decoding ---------------------------------------------------------


def test_decode_value_null_and_unchanged() -> None:
    assert decode_value(TupleColumn("n", None), 23) is None
    from pgtail.pgoutput import is_unchanged

    assert is_unchanged(decode_value(TupleColumn("u", None), 23))


def test_decode_value_int() -> None:
    assert decode_value(TupleColumn("t", b"42"), 23) == 42


def test_decode_value_bool() -> None:
    assert decode_value(TupleColumn("t", b"t"), 16) is True
    assert decode_value(TupleColumn("t", b"f"), 16) is False


def test_decode_value_float_and_numeric() -> None:
    assert decode_value(TupleColumn("t", b"3.14"), 701) == 3.14
    assert decode_value(TupleColumn("t", b"3.14"), 1700) == 3.14


def test_decode_value_text_passthrough() -> None:
    assert decode_value(TupleColumn("t", b"hello"), 25) == "hello"


def test_tuple_to_dict() -> None:
    cols = (
        ColumnSpec(flags=1, name="id", type_oid=23, type_mod=-1),
        ColumnSpec(flags=0, name="email", type_oid=25, type_mod=-1),
    )
    tup = (TupleColumn("t", b"7"), TupleColumn("t", b"a@b.com"))
    d = tuple_to_dict(tup, cols)
    assert d == {"id": 7, "email": "a@b.com"}
