"""Command-line entry point for pgtail."""

from __future__ import annotations

from pathlib import Path

import typer

from pgtail import __version__
from pgtail.collapse import Collapser
from pgtail.connection import ConnectionError_, validate_connection
from pgtail.filters import event_allowed
from pgtail.format import Renderer
from pgtail.options import (
    DEFAULT_OPS,
    DEFAULT_REDACT,
    Settings,
    parse_csv_tuple,
    parse_ops,
)
from pgtail.preflight import PreflightError, run_preflight
from pgtail.replication import drop_slot, stream_changes

app = typer.Typer(
    name="pgtail",
    help="Tail Postgres row changes (INSERT/UPDATE/DELETE) with color.",
    add_completion=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pgtail {__version__}")
        raise typer.Exit(0)


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    dsn: str | None = typer.Argument(
        None,
        metavar="[DSN]",
        help="Postgres connection URL. Falls back to $DATABASE_URL.",
    ),
    schema: str = typer.Option(
        "public",
        "--schema",
        help="Comma-separated schema list to watch.",
    ),
    tables: str | None = typer.Option(
        None,
        "--tables",
        help="Comma-separated table include list (globs allowed: 'order_*').",
    ),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        help="Comma-separated table exclude list (globs allowed).",
    ),
    ops: str = typer.Option(
        ",".join(DEFAULT_OPS),
        "--ops",
        help="Operations to show: insert,update,delete[,truncate].",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit one JSON object per change instead of colored text."
    ),
    no_color: bool = typer.Option(
        False, "--no-color", help="Disable ANSI colors (also honored: NO_COLOR env var)."
    ),
    no_time: bool = typer.Option(False, "--no-time", help="Hide the leading HH:MM:SS timestamp."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Include txid and LSN on each line."
    ),
    max_width: int = typer.Option(
        80, "--max-width", min=10, help="Truncate long values to this many characters."
    ),
    redact: str = typer.Option(
        ",".join(DEFAULT_REDACT),
        "--redact",
        help="Comma-separated column names to mask as '***'.",
    ),
    slot: str | None = typer.Option(
        None,
        "--slot",
        help="Use a persistent replication slot with this name (default: ephemeral).",
    ),
    drop_slot_name: str | None = typer.Option(
        None,
        "--drop-slot",
        help="Drop the named replication slot and exit. Useful for cleaning up after --slot.",
    ),
    log_file: Path | None = typer.Option(  # noqa: B008
        None,
        "--log-file",
        help="Tee plain (no-ANSI) output to this file in addition to stdout.",
    ),
    expand_all: bool = typer.Option(
        False, "--expand-all", help="Do not collapse large transactions."
    ),
    collapse_threshold: int = typer.Option(
        1000,
        "--collapse-threshold",
        min=1,
        help="Collapse a single op on a single table after this many rows.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Tail Postgres row changes with color."""
    resolved_dsn = Settings.resolve_dsn(dsn)
    if drop_slot_name is not None:
        if not resolved_dsn:
            typer.secho(
                "error: --drop-slot needs a DSN (positional arg or $DATABASE_URL).",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        try:
            existed = drop_slot(resolved_dsn, drop_slot_name)
        except Exception as e:  # noqa: BLE001
            typer.secho(f"error: could not drop slot: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(2) from e
        if existed:
            typer.secho(f"dropped replication slot {drop_slot_name!r}.", fg=typer.colors.GREEN)
        else:
            typer.secho(
                f"replication slot {drop_slot_name!r} did not exist.", fg=typer.colors.YELLOW
            )
        raise typer.Exit(0)
    if not resolved_dsn:
        typer.secho(
            "error: no DSN provided. Pass one as an argument or set DATABASE_URL.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    try:
        ops_tuple = parse_ops(ops)
    except ValueError as e:
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from e

    settings = Settings(
        dsn=resolved_dsn,
        schemas=parse_csv_tuple(schema) or ("public",),
        tables=parse_csv_tuple(tables),
        exclude=parse_csv_tuple(exclude),
        ops=ops_tuple,
        json_output=json_output,
        color=Settings.resolve_color(no_color),
        show_time=not no_time,
        verbose=verbose,
        max_width=max_width,
        redact=parse_csv_tuple(redact) or DEFAULT_REDACT,
        slot=slot,
        log_file=log_file,
        expand_all=expand_all,
        collapse_threshold=collapse_threshold,
    )

    try:
        info = validate_connection(settings.dsn)
    except ConnectionError_ as e:
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from e

    try:
        run_preflight(settings.dsn)
    except PreflightError as e:
        typer.secho("preflight check failed:\n", fg=typer.colors.RED, err=True, bold=True)
        typer.secho(str(e), fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(3) from e

    typer.secho(
        f"pgtail → {info.current_database} (user={info.current_user}, "
        f"server_version={info.server_version}). Ctrl-C to stop.",
        fg=typer.colors.CYAN,
        err=True,
    )
    if settings.slot:
        typer.secho(
            f"⚠  using persistent replication slot {settings.slot!r}. "
            "WAL will accumulate on the server while pgtail is not running. "
            f"Run `pgtail {settings.dsn} --drop-slot {settings.slot}` to remove it.",
            fg=typer.colors.YELLOW,
            err=True,
        )

    renderer = Renderer.from_settings(settings)
    collapser = Collapser(settings=settings)
    try:
        for event in stream_changes(settings):
            if not event_allowed(event, settings):
                continue
            for shaped in collapser.process(event):
                renderer.emit(shaped)
        for shaped in collapser.flush():
            renderer.emit(shaped)
    except KeyboardInterrupt:
        typer.secho(
            "\npgtail: stopped (Ctrl-C). cleanup complete.",
            fg=typer.colors.CYAN,
            err=True,
        )
        raise typer.Exit(0) from None
    finally:
        renderer.close()


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
