# --- builder ---
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --no-dev

# --- runtime ---
FROM python:3.13-slim AS runtime
RUN useradd -m appuser
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 9096
USER appuser
# No CMD arg here on purpose - cli.py's Typer app has exactly one command
# (serve), and Typer auto-collapses a single-command app so it runs
# directly with no subcommand name. Passing "serve" explicitly makes Typer
# treat it as an unexpected extra argument and exit with an error - see
# cli.py for the full explanation.
ENTRYPOINT ["tcg-scraper"]
