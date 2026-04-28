"""Render ChangeEvent objects as colored text or JSON lines."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from rich.console import Console
from rich.text import Text

from pgtail.events import ChangeEvent
from pgtail.options import Settings
from pgtail.pgoutput import is_unchanged

# Rich color names by op.
_OP_COLOR = {
    "insert": "green",
    "update": "yellow",
    "delete": "red",
    "truncate": "magenta",
}

# ANSI escape pattern used to strip color when writing to log files.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_value(value: Any, *, max_width: int) -> str:
    """Render a single field value as a short, terminal-friendly string."""
    if value is None:
        return "null"
    if is_unchanged(value):
        return "<unchanged>"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if len(text) > max_width:
        text = text[: max_width - 1] + "\u2026"
    return _quote_if_needed(text, value)


def _quote_if_needed(text: str, original: Any) -> str:
    if isinstance(original, str):
        return f'"{text}"'
    return text


def _format_dict(d: dict[str, Any], *, max_width: int, redact: frozenset[str]) -> str:
    parts: list[str] = []
    for k, v in d.items():
        if k.lower() in redact:
            parts.append(f"{k}: ***")
            continue
        parts.append(f"{k}: {_render_value(v, max_width=max_width)}")
    return "{" + ", ".join(parts) + "}"


def _key_summary(d: dict[str, Any] | None, redact: frozenset[str]) -> str:
    """Pick the row's identity columns for the UPDATE prefix.

    Heuristic: prefer 'id', else first key whose name endswith '_id', else first key.
    """
    if not d:
        return ""
    keys = list(d.keys())
    chosen = None
    if "id" in d:
        chosen = "id"
    else:
        for k in keys:
            if k.endswith("_id"):
                chosen = k
                break
    if chosen is None:
        chosen = keys[0]
    val = d[chosen]
    if chosen.lower() in redact:
        return f"{chosen}=***"
    if val is None:
        return f"{chosen}=null"
    return f"{chosen}={val}"


def _redact_dict(d: dict[str, Any] | None, redact: frozenset[str]) -> dict[str, Any] | None:
    if d is None:
        return None
    return {k: ("***" if k.lower() in redact else v) for k, v in d.items()}


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


@dataclass
class Renderer:
    """Stateful renderer that knows how to emit ChangeEvents to stdout (and optionally a log file)."""

    settings: Settings
    stdout: TextIO
    log_handle: TextIO | None = None
    console: Console | None = None

    @classmethod
    def from_settings(cls, settings: Settings, *, stdout: TextIO | None = None) -> Renderer:
        out = stdout if stdout is not None else sys.stdout
        # Force color off when not a TTY OR when --no-color/$NO_COLOR set.
        use_color = settings.color and (stdout is sys.stdout if stdout else sys.stdout.isatty())
        console = Console(
            file=out,
            force_terminal=use_color,
            color_system="auto" if use_color else None,
            highlight=False,
            soft_wrap=True,
        )
        log_handle: TextIO | None = None
        if settings.log_file:
            path = Path(settings.log_file)
            log_handle = path.open("a", encoding="utf-8")
        return cls(settings=settings, stdout=out, log_handle=log_handle, console=console)

    def close(self) -> None:
        if self.log_handle is not None:
            try:
                self.log_handle.close()
            finally:
                self.log_handle = None

    # ---- main entry ------------------------------------------------------

    def emit(self, event: ChangeEvent) -> None:
        if self.settings.json_output:
            line = self._render_json(event)
            self.stdout.write(line + "\n")
            self.stdout.flush()
            if self.log_handle is not None:
                self.log_handle.write(line + "\n")
                self.log_handle.flush()
            return

        text = self._render_text(event)
        # Write colored to stdout via rich (or plain if no_color / non-TTY).
        if self.console is not None and self.settings.color:
            self.console.print(text)
        else:
            plain = text.plain if isinstance(text, Text) else str(text)
            self.stdout.write(plain + "\n")
            self.stdout.flush()
        if self.log_handle is not None:
            plain = text.plain if isinstance(text, Text) else _strip_ansi(str(text))
            self.log_handle.write(plain + "\n")
            self.log_handle.flush()

    # ---- text rendering --------------------------------------------------

    def _render_text(self, event: ChangeEvent) -> Text:
        s = self.settings
        redact = frozenset(r.lower() for r in s.redact)
        line = Text()

        if s.show_time:
            ts = event.ts.astimezone() if isinstance(event.ts, datetime) else event.ts
            line.append(ts.strftime("%H:%M:%S "), style="dim")

        op_color = _OP_COLOR.get(event.op, "white")
        line.append(event.op.upper().ljust(8), style=f"bold {op_color}")
        line.append(event.qualified, style="bold")

        if s.verbose:
            extra: list[str] = []
            if event.txid is not None:
                extra.append(f"txid={event.txid}")
            if event.lsn:
                extra.append(f"lsn={event.lsn}")
            if extra:
                line.append("  ")
                line.append(" ".join(extra), style="dim")

        if event.op == "truncate":
            if event.truncated_tables:
                line.append("  ")
                line.append(", ".join(event.truncated_tables))
            return line

        if event.op == "insert" and event.new_row is not None:
            line.append("  ")
            line.append(_format_dict(event.new_row, max_width=s.max_width, redact=redact))
            return line

        if event.op == "delete" and event.old_row is not None:
            line.append("  ")
            line.append(_format_dict(event.old_row, max_width=s.max_width, redact=redact))
            return line

        if event.op == "update" and event.new_row is not None:
            key = _key_summary(event.old_row or event.new_row, redact)
            if key:
                line.append("  ")
                line.append(key, style="bold")
            line.append("  ")
            line.append(self._render_update_diff(event, redact))
            return line

        return line

    def _render_update_diff(self, event: ChangeEvent, redact: frozenset[str]) -> str:
        s = self.settings
        if not event.new_row:
            return ""
        new = event.new_row
        old = event.old_row or {}
        fields = event.changed_fields or tuple(new.keys())
        parts: list[str] = []
        for k in fields:
            if k.lower() in redact:
                parts.append(f"{k}: *** \u2192 ***")
                continue
            new_v = new.get(k)
            if is_unchanged(new_v):
                continue
            old_v = old.get(k, "<?>")
            old_s = _render_value(old_v, max_width=s.max_width)
            new_s = _render_value(new_v, max_width=s.max_width)
            parts.append(f"{k}: {old_s} \u2192 {new_s}")
        return ", ".join(parts) if parts else "(no decoded changes)"

    # ---- JSON rendering --------------------------------------------------

    def _render_json(self, event: ChangeEvent) -> str:
        s = self.settings
        redact = frozenset(r.lower() for r in s.redact)
        ts = event.ts.astimezone() if isinstance(event.ts, datetime) else event.ts
        payload: dict[str, Any] = {
            "ts": ts.isoformat(timespec="seconds") if isinstance(ts, datetime) else str(ts),
            "op": event.op,
            "schema": event.schema,
            "table": event.table,
        }
        if s.verbose:
            payload["txid"] = event.txid
            payload["lsn"] = event.lsn
        if event.op == "truncate":
            payload["tables"] = list(event.truncated_tables)
        else:
            new_row = _redact_dict(event.new_row, redact)
            old_row = _redact_dict(event.old_row, redact)
            if new_row is not None:
                payload["new"] = _json_safe(new_row)
            if old_row is not None:
                payload["old"] = _json_safe(old_row)
            if event.op == "update":
                payload["changed"] = list(event.changed_fields)
        return json.dumps(payload, default=str)


def _json_safe(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if is_unchanged(v):
            out[k] = "<unchanged>"
        else:
            out[k] = v
    return out


__all__ = ["Renderer"]
