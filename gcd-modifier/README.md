# gcd-modifier

Fetches the [Grand Comics Database](https://www.comics.org)'s SQLite data dump, filters it down to English-language comics only, and idempotently loads a curated subset of the schema into a `gcd` Postgres database on ComicVault's shared Postgres server.

Sibling service to `comic-scraper`/`tcg-scraper`, same conventions, but batch/cron-driven rather than a live API — nothing calls this service synchronously.

## What it does

1. **Fetch** — logs into comics.org (real Playwright browser session, your own GCD account) and downloads the current SQLite dump (updated roughly every 2 weeks).
2. **Filter** — selects only series where `stddata_language.code = 'en'` and `gcd_series.is_comics_publication` is true, then everything downstream (issues, stories, credits) is scoped to those series.
3. **Load** — upserts the filtered rows (`INSERT ... ON CONFLICT (id) DO UPDATE`, keyed by GCD's own stable ids) into the `gcd` Postgres database, table names matching GCD's own schema. Reruns update changed rows and add new ones without duplicating.

A cron sidecar container runs the full pipeline every 2 weeks so the data stays current automatically.

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
cp .env.example .env   # fill in GCD_USERNAME/GCD_PASSWORD
uv run playwright install --with-deps chromium

uv run gcd-modifier fetch                    # downloads a dump, prints its path
uv run gcd-modifier load --file <dump path>   # filters + loads into Postgres
uv run gcd-modifier run                       # fetch + load in one shot
```

## Docker

Runs as part of the root `comicvault/docker-compose.yml` (service `gcd-modifier`), or standalone via this directory's own `docker-compose.yml` for local iteration against a throwaway Postgres.

The container's default command runs a cron daemon (`cron/entrypoint.sh`) that triggers `gcd-modifier run` every 2 weeks, logging to stdout.
