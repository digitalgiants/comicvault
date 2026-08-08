# Prompt: TCG Card Scanner & Collection — Build Prompt

Paste this whole file as the prompt when ready to start this feature.

**Supersedes:** `feature-requests/pokemon_card_scanner_build_prompt.md` +
`feature-requests/pokemon_card_database_schema.sql` (generalized from
Pokémon-only to any TCG) and `vault/TRADING_CARDS_FEATURE_PROMPT.md` (that
plan deferred scanning to a later phase; this one makes scanning a core
part of v1, folded into the same collection feature). Those three files can
be deleted once this one is in use.

## Project Goal

Add a second, separate collection type to ComicVault for trading cards —
**any TCG** (Pokémon, Magic, One Piece, Yu-Gi-Oh, Digimon, etc.), not
Pokémon-specific. Rename the existing "Collection" nav/section to "Comics"
and add a new "Cards" section alongside it, following the existing
codebase's preference for parallel/duplicated structures over a shared
generic item model (comics and cards are different enough — creator
credits vs. rarity/grading — that forcing one schema would hurt both
sides).

Cards get a scanner from the start: photograph a card → identify it against
a canonical catalog → confirm → add to collection. Build it in phases (see
below) — prove the basic workflow before adding any visual/AI sophistication.

**Naming note:** there's already a `KioskCard` concept in the code — the
customer-facing tile for a comic in the kiosk view. It has nothing to do
with trading cards. Use `TradingCard` / `KioskTradingCardOut` etc.
throughout to avoid ambiguity.

## Decisions already made

- **Scope:** any TCG, not just Pokémon. Card-specific stats (HP, Power,
  Color, attacks, etc.) vary per game and should NOT be fixed columns —
  see "Schema" below.
- **Catalog model:** shared catalog, same pattern as comics — one
  `TradingCard` catalog row per distinct card/printing, personal ownership
  rows link to it (community average price, master photo, dedup on add —
  same as `Comic`/`UserComic`).
- **Kiosk:** trading cards appear in the customer-facing Kiosk (storefront)
  view from the start, not deferred.
- **Catalog/pricing data source:** [apitcg.com](https://apitcg.com) — see
  "External data source" below for its actual schema (confirmed via its
  `openapi.json`). It already surfaces TCGplayer market pricing indirectly
  through its `markets.tcgplayer` field.
- **TCGplayer direct access:** investigated — their docs state they are
  "no longer granting new API access at this time," and no self-serve
  application path could be found. Not pursued for now. If credentials are
  ever obtained (existing developer account, or a partner arrangement),
  TCGplayer's richer Catalog/Pricing/Inventory API can be added as a
  second/upgraded source without reshaping this schema — the importer
  would just gain a second source alongside apitcg.com.
- **OCR/identification approach for v1:** a single call to a
  vision-capable LLM API, asking it to extract structured fields (name,
  number, set, language, variant) from the photo — **not** the classic
  OpenCV corner-detection/perspective-correction/Tesseract pipeline.
  Reasoning: neither `vault/backend` nor `comic-scraper` has any
  image-processing or OCR dependencies today; a vision-LLM call gets a
  working Phase 1 shipped with no new native dependencies, at the cost of
  a per-scan API call instead of self-hosted infra. Revisit a classical CV
  pipeline only if the vision-LLM approach proves too unreliable or too
  costly at real volume.
- **Where the scanner/importer lives:** a new sibling service, e.g.
  `tcg-scraper`, mirroring the existing `comic-scraper` pattern — isolates
  the apitcg.com integration and identification pipeline from the CRUD
  backend. `vault/backend` stays a thin proxy, the same way
  `routes/scan.py` already proxies barcode lookups to `comic_scraper_url`.
- **Schema conventions:** integer primary keys, no Postgres `ENUM` types.
  Reasoning: (1) consistency with every other table in the app (comics,
  users, sales, etc. are all int-PK, no native enums); (2) UUIDs only earn
  their keep when multiple independent systems mint IDs without a central
  authority to reconcile — not the case here, the existing
  `comic-scraper`/`ExternalIssueCache` pattern already proves int PKs +
  `(source, external_id)` external references work fine; (3) Postgres
  `ENUM` types are a real liability now that multi-TCG is confirmed — the
  original doc's `card_category` enum (`Pokemon`/`Trainer`/`Energy`/`Other`)
  is a Pokémon-only in-game concept that doesn't generalize, and `ALTER
  TYPE ... ADD VALUE` doesn't fit this app's idempotent-raw-SQL migration
  style as cleanly as a plain string column does.

## External data source — apitcg.com

Confirmed via its `openapi.json` (the rendered docs page is a JS app that
doesn't expose content to a plain fetch, but the OpenAPI spec behind it
does):

```
GET /api/tcgs                        list of supported games
GET /api/tcgs/{id}                   one game by slug
GET /api/{tcg}/sets                  sets/expansions for a game
GET /api/{tcg}/sets/{id}
GET /api/products                    cards/sealed items/accessories, filterable
GET /api/products/{id}               by numeric id
GET /api/history-prices/{productId}  daily price history
```

Card fields (`type: "card"` products): `_id`, `name`, `description`, `tcg`
(game slug), `serie`, `set`, `images` (small/medium/large URLs),
`dimensions`, `weight`, `release_date`, `markets` (tcgplayer + tcgmatch
pricing), `code` (e.g. `"OP03-070"`), `cardNumber`, `attributes` (dynamic
per-game fields — Rarity, Color, Power, HP, etc. as free-form key/value,
not fixed columns), `createdAt`, `updatedAt`.

Covers: One Piece, Pokémon, Digimon, Magic, Riftbound, Gundam, Dragon Ball
Fusion, Union Arena, "and more" per their landing page. Still need to check
at build time: authentication method, rate limits, and pricing tier —
not disclosed on the pages fetched during planning.

This generic `attributes`-bag shape is exactly why the schema below drops
the original doc's Pokémon-specific fixed columns (`hp`, `stage`,
`regulation_mark`, a dedicated `pokemon` table, `card_attacks`,
`card_abilities`) — apitcg.com's own design already solved "how do I model
wildly different per-game stats generically," and this schema should
mirror that rather than reinvent a Pokémon-only version of it.

## Recommended data model

All tables use integer PKs and plain string columns (no Postgres `ENUM`).
This will live in a new `app/cards/` module in `vault/backend` (its own
`models.py`/`schemas.py`/`crud.py`/`routes.py`), not folded into the
existing flat files — `crud.py` is already ~900 lines and `schemas.py`
~350; adding this much more to those files isn't viable.

**Catalog (shared, populated by the `tcg-scraper` sync job):**
- `card_games` — cache of apitcg's `/api/tcgs` (slug, name, logo) for the
  UI's game picker and FK integrity.
- `card_series` — game_id FK, name, external_id.
- `card_sets` — game_id FK, series_id (nullable FK), name, set_code,
  release_date, symbol/logo image URLs, total_cards, language.
- `trading_cards` — game_id FK, set_id FK, name, card_number, code,
  rarity, language, image_small/medium/large, release_date, description,
  **`attributes` (JSON — dynamic per-game stat bag, mirrors apitcg's own
  field)**, `master_photo` (owner-photo override, mirrors
  `Comic.master_photo`), `average_price` (cached latest market price),
  `created_at`/`updated_at`, `created_by_user_id` (nullable, mirrors
  `Comic.created_by_user_id` for manual catalog additions).
- `trading_card_variants` — card_id FK, variant_type, finish,
  foil_pattern, parallel_type, stamp, stamped_text, alternate_art (bool),
  special_print (bool), description. Direct mirror of the original doc's
  `card_variants` — this part generalizes fine as-is.
- `trading_card_external_ids` — card_id FK, `source` (`'apitcg'`,
  `'tcgplayer'`, ...), `external_id`, `url`. Unique on `(source,
  external_id)` — same pattern as `ExternalIssueCache` for comics.
- `trading_card_images` — card_id FK, variant_id (nullable FK),
  image_type (front/back/reference/variant/scan), image_url, image_hash,
  width, height. For scan reference images and anything beyond the 3 fixed
  catalog sizes.
- `trading_card_prices` — card_id FK, variant_id (nullable FK), source,
  price_type, condition, grader, grade, price, currency, observed_at.
  Current/latest snapshot per source.
- `trading_card_price_history` — same shape, `recorded_at`, for the time
  series. Mirrors/caches apitcg's `/history-prices/{productId}`.

**Personal ownership (mirrors `UserComic`):**
- `user_trading_cards` — user_id FK, card_id FK, variant_id (nullable FK),
  count, condition (plain string, default `'Unknown'`), language,
  storage_location_id (nullable FK), storage_position, point_of_purchase,
  buy_date, paid_price, asking_price, for_sale (bool), personal_img,
  notes, timestamps.
- `card_grades` — user_trading_card_id FK, grader, grade,
  certification_number, graded_date, label_type, population, notes.
  Unique on `(grader, certification_number)`. Kept from the original
  doc as-is — richer than a flat `graded`/`grading_company`/`grade` field
  set, supports multiple submissions/regrades per physical card, applies
  identically across every TCG.
- `card_transactions` — user_trading_card_id (nullable FK, `SET NULL` on
  delete), transaction_type (`Purchase`/`Sale`/`Trade`/`Gift`/`Other` as a
  plain string), transaction_date, source, counterparty, price, shipping,
  tax, fees, total_cost, notes. Kept from the original doc as-is — this is
  a genuine upgrade over comics' `paid_price` field + separate `Sale`
  table, since it can represent trades and gifts. No conflict with the
  comics side; adopt it for cards without trying to retrofit it onto
  comics.
- `card_collection_snapshots` — direct mirror of `CollectionSnapshot`
  (card_count/total_paid/total_value per day per user). Kept separate
  from `trading_card_price_history` — that's market price over time per
  *card*; this is portfolio value over time per *user*. Different axes,
  both useful.

**Identification pipeline:**
- `identification_scans` — user_id FK, image_url (original),
  processed_image_url (nullable), **`raw_response` (JSON — the
  vision-LLM's structured output, replacing the original doc's
  `ocr_text`)**, detected_name, detected_number, detected_set,
  detected_language, detected_variant, detected_game_id (nullable FK),
  created_at.
- `identification_matches` — scan_id FK, candidate_card_id FK,
  candidate_variant_id (nullable FK), confidence, match_method,
  created_at. Unique on `(scan_id, candidate_card_id,
  candidate_variant_id)`.
- Dropped for v1: `identification_observations` (per-field OCR bounding
  boxes) — only meaningful for a classical per-region OCR pipeline, not a
  single vision-LLM call. Revisit if/when a classical CV pipeline is ever
  added.

**Deferred to phase 2 (cheap to add later, not needed for v1):**
- `storage_locations` (name, location_type, parent_location_id,
  description) — nice-to-have, zero schema risk to add later.

**Reused without any schema change (already generic in this codebase):**
- `UserColumnPreference` — already keyed by a generic `page` string; use
  new values (`'cards'`, `'cards_sold'`).
- `KioskFeaturedSet` — already keyed by a generic `section` string; use
  new values (`'cards_todays_picks'`, etc.), with card-specific crud
  lookups behind those section names.
- `CSVImport` — add a `kind` column (`'comics'`/`'cards'`, default
  `'comics'`) instead of a second table, since it only tracks
  filename/counts/errors either way.

A companion `feature-requests/tcg_card_database_schema.sql` gives this
schema as raw SQL for reference. The actual implementation should be
SQLAlchemy models in `app/cards/models.py`, with new tables picked up
automatically by `Base.metadata.create_all()` in `migrate.py` (no explicit
`ALTER TABLE` entries needed for brand-new tables — only for later column
additions to already-deployed tables, per the existing `MIGRATIONS`
pattern).

## Scanning workflow (v1)

```
Photo (phone/browser upload)
    ↓
Store original image
    ↓
Single vision-LLM API call → structured extraction
    (name, number, set, language, variant, confidence self-assessment)
    ↓
Exact/fuzzy match against trading_cards (name + number + set, then game)
    ↓
Candidate list (usually 1, sometimes a few — e.g. same name/number
    printed in multiple sets, or normal vs. reverse-holo)
    ↓
User confirmation screen (photo next to reference image, candidate
    details, confidence)
    ↓
Confirmed → create user_trading_cards record
    ↓
identification_scans / identification_matches store the full history
```

Never silently add a low-confidence identification — always show the
candidate list and require confirmation, per the original doc's Rule 4
("never destroy uncertainty").

## Backend structure

- New `app/cards/` module (`models.py`, `schemas.py`, `crud.py`,
  `routes.py`) inside `vault/backend`, not folded into the existing flat
  files.
- New sibling service `tcg-scraper` (mirrors `comic-scraper`): owns the
  apitcg.com sync job (populating `card_games`/`card_series`/`card_sets`/
  `trading_cards`/`trading_card_prices`) and the identification endpoint
  (`POST /identify` — takes an image, calls the vision-LLM, returns
  extracted fields + candidate matches). `vault/backend`'s
  `routes/cards.py` proxies to it, the same way `routes/scan.py` proxies
  to `comic_scraper_url` today.
- `KioskTradingCardOut` (not `KioskCard`) for the kiosk-facing schema.
- New `utils/card_csv_parser.py` with its own `COLUMN_MAP` for CSV bulk
  import — the header set is unrelated to the comics CSV format.

## Frontend structure

- Reuse the existing table-rendering/column-visibility/pagination shell as
  one generic component parameterized by item kind — that part is
  identical between comics and cards; only the field list and edit-modal
  contents differ.
- `Navbar`: rename "Collection" → "Comics" (`/collection` → `/comics`),
  add a new "Cards" top-level tab (`/cards`), and a "Scan" entry for cards
  (either its own tab or folded into an existing Scan page with a
  Comics/Cards toggle, matching the plan for `Upload`/`Sold`).
- `Upload` and `Sold` pages: in-page Comics/Cards toggle rather than
  doubling the nav with more top-level links.

## Suggested build order

1. Backend models (`app/cards/`) + migration — additive, no risk to
   existing data.
2. `tcg-scraper` service scaffold + apitcg.com sync job for
   games/series/sets/cards (no identification yet) — this is what the
   rest of the feature builds on.
3. Manual add/edit/list/delete + sales for cards (mirrors the comics
   collection CRUD) — proves the schema and UI shell work before adding
   any AI.
4. Frontend nav rename + new Cards collection page (reusing the generic
   table shell).
5. Identification pipeline v1: vision-LLM call → candidate match → user
   confirmation → `user_trading_cards` record. This is the "Phase 1 basic
   scanner" from the original doc, just using a vision-LLM instead of a
   classical OCR/CV pipeline.
6. CSV import (parser + upload route + Upload page toggle).
7. Collection snapshots (dashboard chart gets a Cards line).
8. Kiosk cards section.
9. Only after all of the above is solid and in real use: consider
   whether classical visual matching (image embeddings, reference-image
   comparison) or bulk scanning (many cards in one session) are actually
   worth the added complexity. The original doc's Phase 3–5 ideas
   (weighted confidence scoring, visual embeddings, bulk scan review UI)
   are good long-term direction but not v1 — bulk scanning in particular
   implies background job handling that doesn't exist anywhere in this
   app yet (no Celery/RQ/Redis today).

## Design rules carried over from the original doc (still correct, TCG-general)

1. **The database is authoritative.** The vision-LLM/apitcg.com data
   informs identification; it does not define the catalog.
2. **Identification should be explainable.** Show *why* a candidate was
   chosen (number match, name match, set match), not just a bare
   confidence percentage.
3. **Preserve raw scan data.** Never discard the original photo or the
   raw vision-LLM response — future identification improvements can
   reprocess historical scans.
4. **Never destroy uncertainty.** If unsure, show the candidate list;
   never force an unconfirmed identification into the collection.
5. **Separate canonical cards from physical copies.** `trading_cards` =
   what the card is; `user_trading_cards` = which physical copies someone
   owns (condition, grading, storage, price, transaction history all live
   on the ownership side, never on the catalog row).

## Still open — confirm before writing code

- apitcg.com authentication method, rate limits, and pricing tier — not
  disclosed on the pages checked during planning; needs a real look at
  build time (their Authentication doc page / Developer Platform).
- Which vision-LLM API to call for identification, and its expected
  per-scan cost at your anticipated scan volume.
- Whether `card_games`/`card_series`/`card_sets` should sync from
  apitcg.com on a schedule (like the existing `ExternalSeriesSearchCache`
  TTL pattern for comics) or on-demand — recommend scheduled, since the
  catalog changes slowly and scan-time lookups should hit a local cache,
  not apitcg.com directly.
