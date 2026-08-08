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

## Importing a full catalog

`POST /admin/cards/sync/products/all?game_slug=pokemon` (on `vault/backend`, proxying through here) syncs an entire game's catalog in one paginated pass — confirmed live against apitcg.com: the whole Pokémon catalog is 27,812 products, paginates cleanly at `limit=100`, so a full import costs ~280 calls (~28% of the 1,000/month free-tier quota). Each product embeds its own set info, so sets are resolved/created on the fly — no need to sync sets first, though running `/admin/cards/sync/sets` separately still fills in logo/symbol images and printed totals that the per-product embed doesn't carry.

Check `GET /apitcg/usage` before and after a big sync to see how many calls this process has made (in-process only, resets on restart — see the quota note below).

## Notes / known scaffold simplifications and unverified assumptions

- **apitcg.com's base URL, auth header, and full product schema are now confirmed against a real request** (see `feature-requests/apitcg-calls` for the actual conversation/response this was verified against) — `https://api.apitcg.com/api` (note the `api.` subdomain, easy to miss), `x-api-key` header, and the product shape documented in `api.py`'s `_normalize_product()`. Not guesses anymore.
- **apitcg.com's real rate limit is a 1,000-calls/month quota (free tier), not a per-minute burst.** `APITCG_MAX_CALLS_PER_MINUTE` only throttles bursts within a run; it doesn't track the monthly budget at all. `ApiTcgClient` has an in-process monthly call counter (`APITCG_MONTHLY_CALL_LIMIT`, default 950) that refuses further calls once reached — but it **resets on container restart** and doesn't see calls made outside this process, so it's a safety net against an accidental runaway loop within one run, not a true persistent quota tracker. Check apitcg.com's own dashboard for your real usage before trusting this counter for anything precise.
- **`/api/tcgs` and `/api/{tcg}/sets` item shapes are still unverified** — only the `/api/products` shape was confirmed live. `NormalizedGame`/`NormalizedSet` in `api.py` are still best-guess field mappings; re-check against a real response before relying on set logo/symbol URLs or totals.
- **The `set` query param name for filtering products by set is still unverified** — `search_products(set_id=...)` sends `?set=<id>`, unconfirmed. Not used by the whole-catalog sync path (which needs no set filter), only by the older per-set sync endpoint.
- **No `uv.lock` is committed yet**, same as `comic-scraper` — run `uv lock` locally and commit it, then switch the Dockerfile's `uv sync` calls to `--frozen` for reproducible builds.
- **Ollama model choice is a starting guess, not a verified one.** `moondream` was picked as a small, CPU-friendly vision model, but its availability and its reliability at strict `format: "json"` output haven't been tested against the real Ollama library. This is meant to be the first thing verified when Milestone E work starts — swapping models is a one-line env var change (`OLLAMA_VISION_MODEL`), no code change.
- **No GPU support configured yet.** `docker-compose.yml`'s `ollama` service has a commented-out `deploy.resources.reservations.devices` block for when a GPU is added — uncomment it, no other changes needed.
- **This service intentionally has no persistence layer.** If a future need arises for tcg-scraper itself to cache something durably (not just the in-memory 15-minute TTL cache in `cache.py`), that's a deliberate architecture change, not an oversight — reconsider the stateless design at that point rather than bolting on a database ad hoc.
