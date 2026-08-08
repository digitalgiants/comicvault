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
ENTRYPOINT ["tcg-scraper"]
CMD ["serve"]
