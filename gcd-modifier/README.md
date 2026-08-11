# gcd-modifier

Fetches the [Grand Comics Database](https://www.comics.org)'s SQLite data dump, filters it down to English-language comics only, and idempotently loads a curated subset of the schema into a `gcd` Postgres database on ComicVault's shared Postgres server.

Sibling service to `comic-scraper`/`tcg-scraper`, same conventions, but batch/cron-driven rather than a live API — nothing calls this service synchronously.

## Fetching is manual — comics.org blocks automated logins

comics.org's login page is behind a Cloudflare Turnstile challenge, which detects and blocks Playwright's automated browser session (it serves a "Just a moment..." interstitial instead of the real form). The original plan — `fetch`/`run`, an automated Playwright login — is still in the code (`fetcher.py`) in case that ever changes, but it does not currently work and the cron sidecar does not call it.

Instead:

1. **You download the dump by hand** — log into comics.org yourself in a real browser, accept the license terms, and download the SQLite dump zip (updated roughly every 2 weeks).
2. **Drop it into `dumps/`** — this directory is bind-mounted into the container at `/data/dumps` and gitignored. Drop the `.zip` GCD gives you (or an already-extracted `.db`) in there directly.
3. **`load-latest` picks it up** — filters and loads whichever `.zip`/`.db` in `dumps/` has the newest mtime into Postgres. The cron sidecar runs this every 2 weeks automatically; run it manually any time to load a dump right after dropping it in (see Local development / Docker below).

## What the pipeline does

1. **Filter** — selects only series where `stddata_language.code = 'en'` and `gcd_series.is_comics_publication` is true, then everything downstream (issues, stories, credits) is scoped to those series.
2. **Load** — upserts the filtered rows (`INSERT ... ON CONFLICT (id) DO UPDATE`, keyed by GCD's own stable ids) into the `gcd` Postgres database, table names matching GCD's own schema. Reruns update changed rows and add new ones without duplicating — safe to re-run `load-latest` against the same file, or after dropping in a newer one.

A cron sidecar container runs `load-latest` every 2 weeks so already-dropped-in data stays loaded automatically — it does not fetch anything itself, see above.

## Data license

GCD's data (including its schema/distribution format) is licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Per GCD's own data license page: **private use is unrestricted** — no attribution is required as long as this data stays internal to ComicVault. If it's ever exposed publicly, GCD's crediting guidelines apply.

## Curated schema

Only a subset of GCD's ~50+ tables is loaded — the ones relevant to a comics catalog app:

- `stddata_language`, `stddata_country` — lookups
- `gcd_publisher`, `gcd_indicia_publisher`, `gcd_brand_group`, `gcd_brand`
- `gcd_series` (the filter table), `gcd_issue`
- `gcd_story`, `gcd_story_type`
- `gcd_story_credit`, `gcd_credit_type`, `gcd_creator`, `gcd_creator_name_detail`

See `src/gcd_modifier/models.py` for exact columns.

## Local development

```bash
uv sync
cp .env.example .env   # fill in GCD_USERNAME/GCD_PASSWORD (unused by load-latest, kept for `fetch`/`run`)
uv run playwright install --with-deps chromium

uv run gcd-modifier load --file <dump path>   # filters + loads a specific file into Postgres
uv run gcd-modifier load-latest               # loads whichever file in dumps/ is newest
uv run gcd-modifier fetch                     # automated login - currently blocked, see above
uv run gcd-modifier run                       # fetch + load in one shot - currently blocked, see above
```

## Docker

Runs as part of the root `comicvault/docker-compose.yml` (service `gcd-modifier`), or standalone via this directory's own `docker-compose.yml` for local iteration against a throwaway Postgres.

The root compose file bind-mounts this directory's `dumps/` into the container at `/data/dumps` — drop a manually downloaded dump there directly, no need to exec into the container or copy files across the boundary.

To load a dump right after dropping it in, without waiting for the next cron fire:

```bash
docker compose exec gcd-modifier gcd-modifier load-latest
```

The container's default command runs a cron daemon (`cron/entrypoint.sh`) that triggers `gcd-modifier load-latest` every 2 weeks, logging to stdout.
