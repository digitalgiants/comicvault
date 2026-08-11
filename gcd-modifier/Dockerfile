# --- builder ---
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --no-dev
RUN uv run playwright install --with-deps chromium

# --- runtime ---
FROM python:3.13-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
# playwright install --with-deps in the builder stage installed Chromium's OS-level
# shared libraries (glib, nss, etc.) into the builder's own filesystem, not into the
# browser cache dir copied below - install-deps re-installs just those OS packages
# here, without re-downloading the browser itself.
RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright
COPY --from=builder /app/src /app/src
COPY cron/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
