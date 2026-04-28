"""Large-transaction collapsing.

Tracks per (txid, schema.table, op) counts. Once a key crosses
``settings.collapse_threshold`` rows, subsequent events for the same key are
suppressed and a single summary event is emitted when the txid changes (i.e.
the transaction has committed).

If `--expand-all` is set, the collapser is a no-op.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from pgtail.events import ChangeEvent
from pgtail.options import Settings

_GroupKey = tuple[int | None, str, str]  # (txid, qualified_table, op)


@dataclass
class _Group:
    count: int = 0
    first_event: ChangeEvent | None = None
    suppressed: int = 0  # how many events were swallowed after threshold


@dataclass
class Collapser:
    settings: Settings
    _groups: dict[_GroupKey, _Group] = field(default_factory=dict)
    _current_txid: int | None = None

    def process(self, event: ChangeEvent) -> Iterator[ChangeEvent]:
        if self.settings.expand_all:
            yield event
            return

        # If the transaction id rolled over, flush summaries for the previous one.
        if event.txid is not None and event.txid != self._current_txid:
            yield from self._flush_for_txid(self._current_txid)
            self._current_txid = event.txid

        # TRUNCATE events don't multiply per-row, never collapse.
        if event.op == "truncate":
            yield event
            return

        key: _GroupKey = (event.txid, event.qualified, event.op)
        g = self._groups.setdefault(key, _Group())
        g.count += 1
        if g.first_event is None:
            g.first_event = event

        threshold = self.settings.collapse_threshold
        if g.count <= threshold:
            yield event
        else:
            g.suppressed += 1
            # On the first overshoot, emit a one-time "collapsing remainder" notice.
            if g.suppressed == 1:
                yield self._collapsing_notice(event, g)

    def flush(self) -> Iterator[ChangeEvent]:
        """Emit summaries for any open groups (call at shutdown)."""
        seen_txids = {key[0] for key in self._groups}
        for txid in seen_txids:
            yield from self._flush_for_txid(txid)

    # ---- internals ------------------------------------------------------

    def _flush_for_txid(self, txid: int | None) -> Iterator[ChangeEvent]:
        if txid is None and not self._groups:
            return
        keys_to_drop = [k for k in self._groups if k[0] == txid]
        for key in keys_to_drop:
            g = self._groups.pop(key)
            if g.count > self.settings.collapse_threshold and g.first_event is not None:
                yield self._summary_event(g)

    @staticmethod
    def _collapsing_notice(event: ChangeEvent, g: _Group) -> ChangeEvent:
        return ChangeEvent(
            op=event.op,
            schema=event.schema,
            table=event.table,
            ts=event.ts,
            txid=event.txid,
            lsn=event.lsn,
            extra={"collapse_notice": True, "threshold": g.count - 1},
        )

    @staticmethod
    def _summary_event(g: _Group) -> ChangeEvent:
        first = g.first_event
        assert first is not None
        return ChangeEvent(
            op=first.op,
            schema=first.schema,
            table=first.table,
            ts=first.ts,
            txid=first.txid,
            lsn=first.lsn,
            extra={"collapsed_count": g.count},
        )


__all__ = ["Collapser"]
