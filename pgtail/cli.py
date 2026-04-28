"""Command-line entry point for pgtail."""

from __future__ import annotations

import typer

from pgtail import __version__

app = typer.Typer(
    name="pgtail",
    help="Tail Postgres row changes (INSERT/UPDATE/DELETE) with color.",
    no_args_is_help=False,
    add_completion=False,
)


@app.command()
def run(
    version: bool = typer.Option(False, "--version", help="Print version and exit."),
) -> None:
    """Run pgtail (scaffold — full implementation lands in later tickets)."""
    if version:
        typer.echo(f"pgtail {__version__}")
        raise typer.Exit(0)
    typer.echo("pgtail scaffold — connection and streaming arrive in tickets 002 & 004.")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
