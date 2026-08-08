from __future__ import annotations

import typer
import uvicorn

from tcg_scraper.config import get_settings

app = typer.Typer()


@app.command()
def serve() -> None:
    """Run this as `tcg-scraper`, NOT `tcg-scraper serve`. With only one
    command registered, Typer auto-collapses to "no subcommand name needed"
    mode - passing "serve" explicitly makes it treat that as an unexpected
    extra argument and exit with an error (Dockerfile relies on this: its
    ENTRYPOINT has no CMD arg). If a second command is ever added here,
    Typer will stop collapsing and `tcg-scraper serve` becomes correct
    again - update the Dockerfile's ENTRYPOINT/CMD to match at that point."""
    settings = get_settings()
    uvicorn.run("tcg_scraper.api:app", host="0.0.0.0", port=settings.app_port)


if __name__ == "__main__":
    app()
