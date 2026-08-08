# tcg-scraper

Trading card catalog sync ([apitcg.com](https://apitcg.com)) and photo identification (local [Ollama](https://ollama.com) vision model) for ComicVault's Cards feature. Sibling service to `comic-scraper`, same conventions, but stateless — no database. `vault/backend` persists the real catalog (`trading_cards` etc.) and scan history; this service only proxies apitcg.com and calls Ollama.

## Run with Docker

This service is meant to run as part of the root `docker-compose.yml` stack (alongside `ollama`), not standalone:

```bash
cp .env.example .env   # fill in APITCG_API_KEY
docker compose up -d ollama tcg-scraper
docker compose exec ollama ollama pull moondream   # one-time - see "Model setup" below
```

Service listens on `http://tcg-scraper:9096` inside the compose network (no host port published).

```bash
docker compose exec tcg-scraper curl localhost:9096/health
docker compose exec tcg-scraper curl localhost:9096/games
```

## Model setup (easy to forget)

The `ollama/ollama` image does **not** auto-pull any model on container start. After the `ollama` container is up, run once:

```bash
docker compose exec ollama ollama pull moondream
```

(or whatever `OLLAMA_VISION_MODEL` is set to). Until this is done, `POST /identify` returns `503` with a message telling you to run this — check for that specific error before assuming something else is broken.

## Local dev without Docker

```bash
uv sync
uv run tcg-scraper serve
```

## Notes / known scaffold simplifications and unverified assumptions

- **apitcg.com auth header and base URL are unverified against the real API** — confirmed only via apitcg.com's published `openapi.json`, not a live request with a real key. `APITCG_BASE_URL`/`APITCG_AUTH_HEADER` in `config.py` are best-guess defaults (`https://apitcg.com/api`, `x-api-key` header). If `/games` returns a 502 with an auth-sounding message on first real use, check apitcg.com's actual Authentication docs and adjust the env vars — no code change should be needed.
- **apitcg.com rate limits are undocumented** in what was found during planning. `APITCG_MAX_CALLS_PER_MINUTE` (default 30) is a conservative guess, not a confirmed limit.
- **`/games/{slug}/sets` and product pagination shapes are partially unverified.** The product/card object shape (`_id`, `name`, `tcg`, `serie`, `set`, `images`, `code`, `cardNumber`, `attributes`, `markets`, etc.) is confirmed from apitcg's real OpenAPI spec. The exact shape of `/api/tcgs` and `/api/{tcg}/sets` items, and the pagination envelope on `/api/products` (total count field name, etc.), were not — `api.py`'s normalization functions are defensive about this (falls back to treating the whole response as the item list if no wrapper is found) but should be re-checked against real responses.
- **No `uv.lock` is committed yet**, same as `comic-scraper` — run `uv lock` locally and commit it, then switch the Dockerfile's `uv sync` calls to `--frozen` for reproducible builds.
- **Ollama model choice is a starting guess, not a verified one.** `moondream` was picked as a small, CPU-friendly vision model, but its availability and its reliability at strict `format: "json"` output haven't been tested against the real Ollama library. This is meant to be the first thing verified when Milestone E work starts — swapping models is a one-line env var change (`OLLAMA_VISION_MODEL`), no code change.
- **No GPU support configured yet.** `docker-compose.yml`'s `ollama` service has a commented-out `deploy.resources.reservations.devices` block for when a GPU is added — uncomment it, no other changes needed.
- **This service intentionally has no persistence layer.** If a future need arises for tcg-scraper itself to cache something durably (not just the in-memory 15-minute TTL cache in `cache.py`), that's a deliberate architecture change, not an oversight — reconsider the stateless design at that point rather than bolting on a database ad hoc.
