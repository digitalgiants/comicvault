# coverbrowser-fetcher

Matches GCD's pre-2011 series against [coverbrowser.com](https://www.coverbrowser.com) (a fan-run cover gallery site with no published API) and, once a series is matched with confidence, will pull its cover images for storage alongside ComicVault's own data.

**Current phase: matching only, no image downloading yet.** This crawls coverbrowser's series index and links it to GCD series where it's confident, or queues anything ambiguous for manual review. Pulling and storing actual cover images is a separate, later phase built on top of a trustworthy match table.

## Why pre-2011 only

coverbrowser has no year or publisher metadata anywhere in its index, and per-cover pages expose no publisher or date either - just an issue number and an image path. During design, a real check of `/covers/batman` found its listing caps out at the classic Volume 1 run (#1-713, ending 2011) with no New 52 or Rebirth content, and no separate slug exists for those later volumes. Rather than build matching logic for coverage that doesn't exist, this is scoped to GCD series with `year_began` before a cutoff (2011 by default, see `match --cutoff-year`).

## Why matching is conservative

There's no shared id between GCD and coverbrowser - titles are the only link, and titles collide. With no publisher or date available to disambiguate, a match is only auto-accepted when:

1. Exactly one coverbrowser slug has the same normalized title as the GCD series (no ambiguity to guess through), and
2. Its cover count is a plausible multiple of GCD's issue count, and
3. A live fetch of that slug's page 1 actually contains the series' first issue number.

Anything short of all three is written to `series_match_candidate` for a human to resolve later, never guessed. See `matcher.py`'s module docstring for the full reasoning.

## Rate limiting

coverbrowser has no published API or rate-limit policy, and returned a 429 after only a handful of manual requests made while designing this. `ThrottledClient` (`crawler.py`) is single-threaded on purpose - no concurrency, unlike the Metron/ComicVine work elsewhere in this project - with a fixed delay between every request (`REQUEST_DELAY_SECONDS`, default 2.5s) and a real, honest `User-Agent`. A 403/429 stops the whole run immediately rather than retrying.

## Usage

```bash
uv sync
cp .env.example .env   # fill in GCD_DATABASE_URL

uv run coverbrowser-fetcher index          # crawl the 27 /a-z/<bucket> pages into series_index
uv run coverbrowser-fetcher match          # match GCD series (year_began < 2011) against series_index
uv run coverbrowser-fetcher match --limit 20   # test against a small batch first
```

`index` is safe to re-run (upserts by slug). `match` skips any GCD series already resolved (in `series_match` or `series_match_candidate`), so re-running it only processes series added since the last run.

## Docker

Runs as part of the root `comicvault/docker-compose.yml` (service `coverbrowser-fetcher`) - a one-shot CLI, not a long-running server, so it's invoked directly rather than auto-started:

```bash
docker compose run --rm coverbrowser-fetcher index
docker compose run --rm coverbrowser-fetcher match
```
