from __future__ import annotations

import logging

import typer
import uvicorn

from comic_scraper.cache import LookupCache
from comic_scraper.config import get_settings
from comic_scraper.lookup import UpcLookupService
from comic_scraper.metron.client import MetronClient

app = typer.Typer()


@app.command()
def serve() -> None:
    settings = get_settings()
    uvicorn.run("comic_scraper.api:app", host="0.0.0.0", port=settings.app_port)


@app.command()
def lookup(upc12: str, ean5: str = typer.Argument(None)) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    with MetronClient(
        settings.metron_username,
        settings.metron_password,
        settings.metron_base_url,
        settings.metron_max_calls_per_minute,
    ) as client:
        cache = LookupCache(settings.database_url)
        result = UpcLookupService(client, cache).lookup(upc12, ean5)
        if result is None:
            typer.echo(f"No issue found for UPC {upc12}")
            raise typer.Exit(code=1)
        typer.echo(result.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
