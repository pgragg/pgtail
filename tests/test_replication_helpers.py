"""Tests for replication module pieces that don't need a live DB."""

from __future__ import annotations

import struct

from pgtail.replication import (
    _build_status_update,
    _lsn_to_str,
    _parse_xlog_or_keepalive,
)


def test_lsn_to_str() -> None:
    assert _lsn_to_str(0) == "0/0"
    # 0x0000_0001_DEAD_BEEF -> "1/DEADBEEF"
    assert _lsn_to_str((1 << 32) | 0xDEADBEEF).upper() == "1/DEADBEEF"


def test_status_update_shape() -> None:
    msg = _build_status_update(0xABCD, request_reply=True)
    assert msg[:1] == b"r"
    assert len(msg) == 1 + 8 * 4 + 1
    last, flushed, applied, _ts = struct.unpack(">QQQQ", msg[1:33])
    assert last == flushed == applied == 0xABCD
    assert msg[-1:] == b"\x01"


def test_parse_keepalive() -> None:
    raw = b"k" + struct.pack(">QQB", 0xFF, 1234, 1)
    kind, fields = _parse_xlog_or_keepalive(raw)
    assert kind == "k"
    assert fields["wal_end"] == 0xFF
    assert fields["reply_requested"] is True


def test_parse_xlog_data() -> None:
    payload = b"hello"
    raw = b"w" + struct.pack(">QQQ", 1, 2, 3) + payload
    kind, fields = _parse_xlog_or_keepalive(raw)
    assert kind == "w"
    assert fields["wal_start"] == 1
    assert fields["wal_end"] == 2
    assert fields["payload"] == payload
