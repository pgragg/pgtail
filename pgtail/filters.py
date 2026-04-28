"""Client-side filtering: schema/table glob matching, op filtering, system-schema hiding.

Publication-side filtering happens in `replication._resolve_tables`. We also
filter on the client to support `--exclude` (CREATE PUBLICATION lacks an
EXCLUDE clause) and to hide system schemas regardless of the publication
configuration.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable

from pgtail.events import ChangeEvent
from pgtail.options import Settings

# Schemas hidden unless the user explicitly opts into them via --schema.
SYSTEM_SCHEMAS: frozenset[str] = frozenset({"pg_catalog", "information_schema", "pg_toast"})


def _glob_match_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def schema_allowed(schema: str, settings: Settings) -> bool:
    """Return True if events from this schema should be shown."""
    if not schema:
        return True  # truncate placeholder events with no schema fallthrough
    if schema in SYSTEM_SCHEMAS and schema not in settings.schemas:
        return False
    return not (settings.schemas and schema not in settings.schemas)


def table_allowed(table: str, settings: Settings) -> bool:
    """Return True if events for this table should be shown.

    Include rules: if `--tables` is non-empty, the table must match at least one pattern.
    Exclude rules: if `--exclude` matches, the table is dropped regardless of include.
    """
    if settings.exclude and _glob_match_any(table, settings.exclude):
        return False
    return not (settings.tables and not _glob_match_any(table, settings.tables))


def op_allowed(op: str, settings: Settings) -> bool:
    return op in settings.ops


def event_allowed(event: ChangeEvent, settings: Settings) -> bool:
    """Composite predicate: should this event be emitted?"""
    if not op_allowed(event.op, settings):
        return False
    # TRUNCATE events synthesize schema/table from the first relation; if that
    # relation is filtered out, drop the event.
    if event.op == "truncate" and event.truncated_tables:
        keep_any = False
        for fq in event.truncated_tables:
            if "." in fq:
                ns, tbl = fq.split(".", 1)
            else:
                ns, tbl = "", fq
            if schema_allowed(ns, settings) and table_allowed(tbl, settings):
                keep_any = True
                break
        return keep_any
    if not schema_allowed(event.schema, settings):
        return False
    return table_allowed(event.table, settings)


def redact_set(settings: Settings) -> frozenset[str]:
    """Return the case-folded set of column names to redact."""
    return frozenset(r.lower() for r in settings.redact)
