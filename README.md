# ComicVault

A web app for cataloging and managing a comic book and trading card shop's inventory — a shared catalog of comics/cards, personal (per-user) ownership and sale tracking, barcode/photo-based scanning to add items quickly, and a customer-facing kiosk view.

## Architecture

Seven services, run together via the root `docker-compose.yml`:

| Service | What it does | Port (internal) |
|---|---|---|
| `frontend` | React + TypeScript UI | `3002 -> 3000` (published) |
| `backend` | FastAPI app — the API, database models, and all business logic | `8000` (published) |
| `postgres` | Shared Postgres server — separate databases for `backend` (`comicvault`), `comic-scraper` (`comic_scraper`), and `gcd-modifier` (`gcd`) | internal only |
| `comic-scraper` | Sibling service: UPC/EAN-5 comic issue lookup against the Metron API, used by the comics barcode scanner | `9095`, internal only |
| `tcg-scraper` | Sibling service: trading card catalog sync against [apitcg.com](https://apitcg.com) and photo identification via a local Ollama vision model | `9096`, internal only |
| `ollama` | Self-hosted vision-LLM runtime, used by `tcg-scraper` for card photo identification | `11434`, internal only |
| `gcd-modifier` | Sibling service: loads a manually-downloaded Grand Comics Database dump on a schedule, filters to English-language comics, loads into its own `gcd` database | cron-driven, no port |

`backend` is the only service with a real database schema — `comic-scraper` and `tcg-scraper` are both external-API proxies (see their own READMEs for why), and `gcd-modifier` is a batch writer to its own isolated database. `backend` talks to `comic-scraper`/`tcg-scraper` over HTTP; nothing else talks to Postgres directly except `backend`, `comic-scraper`, and `gcd-modifier`. Nothing currently reads from the `gcd` database — it's populated and ready for `backend` (or another service) to query later.

```
Browser
  |
frontend (React)
  |
backend (FastAPI) ---- postgres (comicvault DB)
  |         |
  |         +--> comic-scraper --> Metron API           (comics barcode lookup)
  |                   |
  |                   +--> postgres (comic_scraper DB)
  |
  +--> tcg-scraper --> apitcg.com                        (card catalog sync)
            |
            +--> ollama (local vision model)              (card photo identification)

you (manual download) --> gcd-modifier/dumps/ --> gcd-modifier (cron, every 2 weeks) --> postgres (gcd DB)
```

## Features

### Comics
- **Collection** (`/comics`) — search/filter/paginate your comics, edit personal fields (condition, price, notes), record sales, upload a photo of your own copy.
- **Upload** (`/upload`) — bulk-import a collection via CSV.
- **Scan** (`/scan`) — photograph or type a UPC barcode, look it up via `comic-scraper` (Metron), review/edit the pre-filled fields, add to your collection.
- **Search** (`/search`) — look up a series by title (Metron + ComicVine) and add an issue directly, without a barcode.
- **Sold** (`/sold`) — your sales history.
- **Kiosk** (`/kiosk`) — a separate customer-facing, read-only storefront view for a dedicated `is_kiosk` account, with a Comics/Cards toggle. Comics side: "Today's Picks" (price threshold) and "Signed Comics" featured sections, plus series-title search/browse. Cards side: "Today's Picks" and "Graded Cards" featured sections, plus card-name search/browse — deliberately minimal detail (no grade/condition shown to customers even in the Graded Cards section). The two are separate sections, not a merged feed.
- **Admin** (`/admin`, requires `is_admin`) — manage users, manually add/edit shared catalog comics, review bug reports, and (Cards Sync tab) trigger the apitcg.com catalog sync.

### Cards (any TCG — Pokémon, Magic, One Piece, etc.)
- **Collection** (`/cards`) — same shape as the Comics collection: search/filter, edit ownership fields, record sales, upload your own photo.
- **Add Card** — search the already-synced catalog by name and add a copy to your collection. (There's no self-service catalog *creation* for regular users — only admins can add new catalog cards, via `POST /admin/cards` or a sync below.)
- **Scan Card** — photograph a card, get identified via a local Ollama vision model, review candidate matches (with confidence scores), confirm to add to your collection. Falls back to manual search if nothing matches confidently. See `tcg-scraper/README.md` for exactly how this pipeline works and what's still unverified against real hardware/models. A bug that returned zero candidates whenever the vision model only read the printed card number (common with the small default model on smaller name/set text) is fixed via a number-only fallback match tier.
- **Catalog sync** — Admin dashboard's "Cards Sync" tab: sync games, pick one, sync its sets (optional) and/or its full catalog in one paginated pass. Same actions are also directly callable: `POST /admin/cards/sync/games`, `/admin/cards/sync/sets`, `/admin/cards/sync/products` (one set), `/admin/cards/sync/products/all` (a whole game's catalog in one pass — recommended for a first import, see `tcg-scraper/README.md` for the apitcg.com quota cost).
- **Kiosk** — see the Kiosk bullet above.

Cards still don't have CSV import or collection snapshots/analytics. See `feature-requests/` (gitignored, local-only) for the original build plan and phasing if you're picking this back up.

## Quick start

```bash
cp .env.example .env
# fill in JWT_SECRET, KIOSK_PASSWORD, METRON_USERNAME/PASSWORD, APITCG_API_KEY

docker compose up -d --build
docker compose exec ollama ollama pull moondream   # one-time - see tcg-scraper/README.md
```

- Frontend: `http://localhost:3002`
- Backend API docs: `http://localhost:8000/docs`

`backend`'s container command runs `migrate.py` automatically on every start (idempotent — safe to run repeatedly), so the schema is created/updated before `uvicorn` starts. There's no separate migration step to remember.

First real use of Cards needs the catalog synced first (see "Catalog sync" above) — until that's done, card search and the scanner will find nothing, since the scanner only matches against your own synced catalog, not apitcg.com live.

## Configuration

Root `.env` (loaded by `docker-compose.yml`):

| Variable | Used by | Notes |
|---|---|---|
| `JWT_SECRET` | `backend` | Required, no default worth keeping in production |
| `KIOSK_PASSWORD` | `backend` | Password for the auto-created `kiosk` account |
| `METRON_USERNAME` / `METRON_PASSWORD` | `comic-scraper` | [metron.cloud](https://metron.cloud) credentials |
| `APITCG_API_KEY` | `tcg-scraper` | [apitcg.com](https://apitcg.com) API key |
| `OLLAMA_VISION_MODEL` | `tcg-scraper` | Default `moondream` (small/CPU-friendly) — swap once a GPU is available, see `tcg-scraper/README.md` |
| `GCD_USERNAME` / `GCD_PASSWORD` | `gcd-modifier` | [comics.org](https://www.comics.org) account credentials, used to log in and download the GCD data dump |

`vault/backend/.env.example`, `tcg-scraper/.env.example`, and `gcd-modifier/.env.example` document each service's full settings (most have working defaults already baked into `docker-compose.yml`).

## Directory structure

```
comicvault/
├── docker-compose.yml
├── vault/
│   ├── backend/          FastAPI app (see below)
│   └── frontend/         React + TypeScript UI
├── comic-scraper/        Sibling service - comics barcode lookup (Metron)
├── tcg-scraper/          Sibling service - card catalog sync + photo ID (apitcg.com, Ollama)
├── gcd-modifier/         Sibling service - Grand Comics Database dump fetch/filter/load, cron-driven
└── postgres-init/        One-time init SQL (creates the comic-scraper and gcd DBs on a fresh volume)
```

`vault/backend/app/` follows a flat-file convention deliberately, not a per-feature package layout: `models.py` (all SQLAlchemy models), `schemas.py` (all Pydantic schemas), `crud.py` (comics CRUD) / `crud_cards.py` (cards CRUD, split out only because `crud.py` was already large), and one file per feature under `routes/`.

## Local development

Each service can run outside Docker too — see `tcg-scraper/README.md` and `comic-scraper/README.md` for their own local-dev instructions (both use `uv`). For `vault/backend`/`vault/frontend`, running via `docker compose` with the bind-mounted source (already configured) and editing locally is the simplest loop — `backend`'s `uvicorn --reload` and `frontend`'s Vite dev server both pick up changes live.

## Known gaps / current state

- Cards have no CSV import and no collection snapshots/analytics (comics have both). Kiosk and catalog-sync UI are done.
- Card scanning previously returned zero match candidates whenever the vision model could only read the printed card number - fixed with a number-only fallback match tier (see the Scan Card bullet above). Check `docker compose logs tcg-scraper` first if a scan still comes back empty.
- The apitcg.com integration has been verified against a real captured API response (including a couple of real bugs found and fixed that way - see `tcg-scraper/README.md`).
- The frontend is responsive down to phone width (~375px) and tablet (~768px) - the main nav collapses into a hamburger menu below the `md` breakpoint and is sticky on every page.
- `gcd-modifier`'s dump fetch is manual, not automated - comics.org's login is behind a Cloudflare Turnstile challenge that blocks headless browsers. Download the dump yourself and drop it in `gcd-modifier/dumps/` (bind-mounted, gitignored); the cron sidecar loads whichever file is newest every 2 weeks. See `gcd-modifier/README.md`.
