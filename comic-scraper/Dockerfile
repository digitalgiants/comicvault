# --- frontend builder ---
FROM node:24-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

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
COPY --from=frontend-builder /frontend/dist /app/static
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 9095
USER appuser
ENTRYPOINT ["comic-scraper"]
CMD ["serve"]
