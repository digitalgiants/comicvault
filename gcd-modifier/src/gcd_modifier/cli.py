from __future__ import annotations

import logging
from pathlib import Path

import typer

from gcd_modifier.config import get_settings
from gcd_modifier.fetcher import fetch_dump
from gcd_modifier.loader import load_dump

app = typer.Typer()


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def fetch() -> None:
    """Log into comics.org and download the current GCD SQLite dump."""
    _configure_logging()
    settings = get_settings()
    dump_path = fetch_dump(settings.gcd_base_url, settings.gcd_username, settings.gcd_password, settings.dump_dir)
    typer.echo(str(dump_path))


@app.command()
def load(file: Path = typer.Option(..., "--file", exists=True, help="Path to a GCD SQLite dump")) -> None:
    """Filter a GCD SQLite dump to English-language comics and load it into Postgres."""
    _configure_logging()
    settings = get_settings()
    load_dump(file, settings.database_url)


@app.command()
def run() -> None:
    """Fetch the latest GCD dump and load it in one shot -- what the cron sidecar calls."""
    _configure_logging()
    settings = get_settings()
    dump_path = fetch_dump(settings.gcd_base_url, settings.gcd_username, settings.gcd_password, settings.dump_dir)
    load_dump(dump_path, settings.database_url)


if __name__ == "__main__":
    app()
