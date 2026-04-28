"""ChangeEvent dataclass and related types — the unit of work pgtail produces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Op = Literal["insert", "update", "delete", "truncate"]


@dataclass(frozen=True)
class ColumnMeta:
    name: str
    type_oid: int
    type_mod: int
    is_key: bool  # part of replica identity


@dataclass(frozen=True)
class RelationMeta:
    oid: int
    schema: str
    name: str
    replica_identity: str  # 'd' default, 'n' nothing, 'f' full, 'i' index
    columns: tuple[ColumnMeta, ...]

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass(frozen=True)
class ChangeEvent:
    op: Op
    schema: str
    table: str
    ts: datetime
    txid: int | None = None
    lsn: str | None = None
    # For INSERT: new_row populated. For DELETE: old_row populated.
    # For UPDATE: both populated when REPLICA IDENTITY FULL or key change; otherwise
    # old_row holds at least the replica-identity columns.
    new_row: dict[str, Any] | None = None
    old_row: dict[str, Any] | None = None
    # Keys that changed in an UPDATE (computed when both rows are available).
    changed_fields: tuple[str, ...] = ()
    # Set on TRUNCATE: list of qualified table names included in this op.
    truncated_tables: tuple[str, ...] = ()
    # Internal hint from collapser (ticket 007).
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.table}"
