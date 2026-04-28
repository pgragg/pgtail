"""Pure decoder for the Postgres pgoutput logical replication protocol (v1).

We parse only what pgtail needs:
  Begin (B), Commit (C), Origin (O), Relation (R), Type (Y),
  Insert (I), Update (U), Delete (D), Truncate (T).

Reference: https://www.postgresql.org/docs/current/protocol-logicalrep-message-formats.html

This module deliberately has no I/O so it can be unit-tested with byte fixtures.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

# Postgres epoch is 2000-01-01 00:00:00 UTC.
_PG_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


def _pg_ts_to_datetime(micros_since_2000: int) -> datetime:
    return _PG_EPOCH + timedelta(microseconds=micros_since_2000)


# --- low-level reader ---------------------------------------------------------


class _Reader:
    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes) -> None:
        self.buf = buf
        self.pos = 0

    def remaining(self) -> int:
        return len(self.buf) - self.pos

    def read(self, n: int) -> bytes:
        if self.pos + n > len(self.buf):
            raise ValueError(f"pgoutput: short read ({n} bytes, {self.remaining()} remaining)")
        out = self.buf[self.pos : self.pos + n]
        self.pos += n
        return out

    def read_u8(self) -> int:
        return self.read(1)[0]

    def read_i16(self) -> int:
        return struct.unpack(">h", self.read(2))[0]

    def read_u32(self) -> int:
        return struct.unpack(">I", self.read(4))[0]

    def read_i32(self) -> int:
        return struct.unpack(">i", self.read(4))[0]

    def read_i64(self) -> int:
        return struct.unpack(">q", self.read(8))[0]

    def read_u64(self) -> int:
        return struct.unpack(">Q", self.read(8))[0]

    def read_cstring(self) -> str:
        end = self.buf.index(b"\x00", self.pos)
        s = self.buf[self.pos : end].decode("utf-8")
        self.pos = end + 1
        return s


# --- decoded message dataclasses ---------------------------------------------


@dataclass(frozen=True)
class BeginMsg:
    final_lsn: int
    commit_ts: datetime
    xid: int


@dataclass(frozen=True)
class CommitMsg:
    flags: int
    commit_lsn: int
    end_lsn: int
    commit_ts: datetime


@dataclass(frozen=True)
class OriginMsg:
    commit_lsn: int
    name: str


@dataclass(frozen=True)
class ColumnSpec:
    flags: int  # bit 1 = part of replica identity key
    name: str
    type_oid: int
    type_mod: int

    @property
    def is_key(self) -> bool:
        return bool(self.flags & 0x01)


@dataclass(frozen=True)
class RelationMsg:
    oid: int
    namespace: str
    name: str
    replica_identity: str  # 'd', 'n', 'f', 'i'
    columns: tuple[ColumnSpec, ...]


@dataclass(frozen=True)
class TypeMsg:
    type_oid: int
    namespace: str
    name: str


@dataclass(frozen=True)
class TupleColumn:
    kind: str  # 'n' null, 'u' unchanged-toast, 't' text, 'b' binary
    value: bytes | None  # raw bytes for 't'/'b', else None


@dataclass(frozen=True)
class InsertMsg:
    relation_oid: int
    new_tuple: tuple[TupleColumn, ...]


@dataclass(frozen=True)
class UpdateMsg:
    relation_oid: int
    # Old tuple is present if REPLICA IDENTITY != DEFAULT, or a key column changed.
    # When DEFAULT and no key change, only new_tuple is sent.
    old_tuple: tuple[TupleColumn, ...] | None
    old_kind: str | None  # 'K' (key only), 'O' (old full), or None
    new_tuple: tuple[TupleColumn, ...]


@dataclass(frozen=True)
class DeleteMsg:
    relation_oid: int
    old_tuple: tuple[TupleColumn, ...]
    old_kind: str  # 'K' or 'O'


@dataclass(frozen=True)
class TruncateMsg:
    flags: int  # 1=CASCADE, 2=RESTART IDENTITY
    relation_oids: tuple[int, ...]


PgOutputMessage = (
    BeginMsg
    | CommitMsg
    | OriginMsg
    | RelationMsg
    | TypeMsg
    | InsertMsg
    | UpdateMsg
    | DeleteMsg
    | TruncateMsg
)


# --- decoder ------------------------------------------------------------------


def _read_tuple(r: _Reader) -> tuple[TupleColumn, ...]:
    n = r.read_i16()
    cols: list[TupleColumn] = []
    for _ in range(n):
        kind = chr(r.read_u8())
        if kind == "n":
            cols.append(TupleColumn("n", None))
        elif kind == "u":
            cols.append(TupleColumn("u", None))
        elif kind in ("t", "b"):
            length = r.read_u32()
            data = r.read(length)
            cols.append(TupleColumn(kind, data))
        else:  # pragma: no cover — protocol violation
            raise ValueError(f"pgoutput: unknown tuple-column kind {kind!r}")
    return tuple(cols)


def decode_message(payload: bytes) -> PgOutputMessage:
    """Decode a single pgoutput message payload (without WAL framing).

    Raises ValueError if the type byte is unsupported.
    """
    if not payload:
        raise ValueError("pgoutput: empty payload")
    r = _Reader(payload)
    type_byte = chr(r.read_u8())

    if type_byte == "B":
        final_lsn = r.read_u64()
        commit_ts = _pg_ts_to_datetime(r.read_i64())
        xid = r.read_u32()
        return BeginMsg(final_lsn=final_lsn, commit_ts=commit_ts, xid=xid)

    if type_byte == "C":
        flags = r.read_u8()
        commit_lsn = r.read_u64()
        end_lsn = r.read_u64()
        commit_ts = _pg_ts_to_datetime(r.read_i64())
        return CommitMsg(flags=flags, commit_lsn=commit_lsn, end_lsn=end_lsn, commit_ts=commit_ts)

    if type_byte == "O":
        commit_lsn = r.read_u64()
        name = r.read_cstring()
        return OriginMsg(commit_lsn=commit_lsn, name=name)

    if type_byte == "R":
        oid = r.read_u32()
        namespace = r.read_cstring()
        name = r.read_cstring()
        replica_identity = chr(r.read_u8())
        ncols = r.read_i16()
        cols: list[ColumnSpec] = []
        for _ in range(ncols):
            flags = r.read_u8()
            cname = r.read_cstring()
            type_oid = r.read_u32()
            type_mod = r.read_i32()
            cols.append(ColumnSpec(flags=flags, name=cname, type_oid=type_oid, type_mod=type_mod))
        return RelationMsg(
            oid=oid,
            namespace=namespace,
            name=name,
            replica_identity=replica_identity,
            columns=tuple(cols),
        )

    if type_byte == "Y":
        type_oid = r.read_u32()
        namespace = r.read_cstring()
        name = r.read_cstring()
        return TypeMsg(type_oid=type_oid, namespace=namespace, name=name)

    if type_byte == "I":
        oid = r.read_u32()
        marker = chr(r.read_u8())
        if marker != "N":
            raise ValueError(f"pgoutput: INSERT expected 'N' marker, got {marker!r}")
        new_tuple = _read_tuple(r)
        return InsertMsg(relation_oid=oid, new_tuple=new_tuple)

    if type_byte == "U":
        oid = r.read_u32()
        old_kind: str | None = None
        old_tuple: tuple[TupleColumn, ...] | None = None
        marker = chr(r.read_u8())
        if marker in ("K", "O"):
            old_kind = marker
            old_tuple = _read_tuple(r)
            marker = chr(r.read_u8())
        if marker != "N":
            raise ValueError(f"pgoutput: UPDATE expected 'N' marker, got {marker!r}")
        new_tuple = _read_tuple(r)
        return UpdateMsg(
            relation_oid=oid, old_tuple=old_tuple, old_kind=old_kind, new_tuple=new_tuple
        )

    if type_byte == "D":
        oid = r.read_u32()
        marker = chr(r.read_u8())
        if marker not in ("K", "O"):
            raise ValueError(f"pgoutput: DELETE expected 'K' or 'O' marker, got {marker!r}")
        old_tuple = _read_tuple(r)
        return DeleteMsg(relation_oid=oid, old_tuple=old_tuple, old_kind=marker)

    if type_byte == "T":
        n_rel = r.read_u32()
        flags = r.read_u8()
        oids = tuple(r.read_u32() for _ in range(n_rel))
        return TruncateMsg(flags=flags, relation_oids=oids)

    raise ValueError(f"pgoutput: unsupported message type {type_byte!r}")


# --- value decoding -----------------------------------------------------------

# Type OIDs we render specially when emitting JSON / structured output.
# All other types fall back to the raw text representation Postgres provides.
_BOOL_OIDS = frozenset({16})
_INT_OIDS = frozenset({20, 21, 23, 26})  # int8, int2, int4, oid
_FLOAT_OIDS = frozenset({700, 701})  # float4, float8
_NUMERIC_OID = 1700
_JSON_OIDS = frozenset({114, 3802})  # json, jsonb


def decode_value(col: TupleColumn, type_oid: int) -> Any:
    """Convert a TupleColumn into a Python value for display / JSON output."""
    if col.kind == "n":
        return None
    if col.kind == "u":
        # "Unchanged TOAST" sentinel — we don't have the value.
        return _UNCHANGED
    assert col.value is not None
    text = col.value.decode("utf-8", errors="replace") if col.kind == "t" else col.value.hex()

    if col.kind == "b":
        # Binary mode is rare in pgoutput; surface as hex string.
        return text

    if type_oid in _BOOL_OIDS:
        return text == "t"
    if type_oid in _INT_OIDS:
        try:
            return int(text)
        except ValueError:
            return text
    if type_oid in _FLOAT_OIDS or type_oid == _NUMERIC_OID:
        try:
            return float(text)
        except ValueError:
            return text
    if type_oid in _JSON_OIDS:
        # Keep raw text — let downstream pretty-printer decide.
        return text
    return text


class _Unchanged:
    """Sentinel for TOASTed columns whose value the publisher did not include."""

    _instance: _Unchanged | None = None

    def __new__(cls) -> _Unchanged:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover
        return "<unchanged-toast>"

    def __str__(self) -> str:
        return "<unchanged>"


_UNCHANGED = _Unchanged()


def is_unchanged(value: Any) -> bool:
    return value is _UNCHANGED


def tuple_to_dict(tup: tuple[TupleColumn, ...], columns: tuple[ColumnSpec, ...]) -> dict[str, Any]:
    """Zip a decoded tuple against a relation's column metadata."""
    if len(tup) != len(columns):
        raise ValueError(f"pgoutput: tuple has {len(tup)} cols but relation has {len(columns)}")
    return {col.name: decode_value(t, col.type_oid) for t, col in zip(tup, columns, strict=True)}
