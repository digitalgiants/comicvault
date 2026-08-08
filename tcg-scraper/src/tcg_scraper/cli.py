from __future__ import annotations

import typer
import uvicorn

from tcg_scraper.config import get_settings

app = typer.Typer()


@app.command()
def serve() -> None:
    settings = get_settings()
    uvicorn.run("tcg_scraper.api:app", host="0.0.0.0", port=settings.app_port)


if __name__ == "__main__":
    app()
