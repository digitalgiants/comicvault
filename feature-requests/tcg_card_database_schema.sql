-- TCG Card Collection Database (generalized from the Pokemon-only draft)
-- PostgreSQL 14+
-- Reference schema for planning purposes. The actual implementation should
-- be SQLAlchemy models in vault/backend/app/cards/models.py, following the
-- same int-PK, no-native-ENUM convention as the rest of ComicVault, picked
-- up by Base.metadata.create_all() in migrate.py. This file exists so the
-- shape is concrete and reviewable before that translation happens.
--
-- Differences from feature-requests/pokemon_card_database_schema.sql:
--   * Integer PKs instead of UUIDs (matches every other table in the app).
--   * No Postgres ENUM types (card_language, card_category, condition_grade,
--     transaction_type all become plain TEXT) - card_category in particular
--     was Pokemon-specific ('Pokemon'/'Trainer'/'Energy'/'Other') and can't
--     generalize to other games as a fixed type.
--   * Dropped the Pokemon-only fixed-column modeling (pokemon table,
--     card_attacks, card_abilities, hp/stage/regulation_mark columns) in
--     favor of a generic `attributes` JSON column on trading_cards, mirroring
--     how apitcg.com itself models per-game stats as a dynamic bag rather
--     than fixed columns.
--   * Added card_games / renamed series->card_series, sets->card_sets to
--     avoid colliding with plain English words in a multi-table schema.
--   * Dropped identification_observations (per-field OCR bounding boxes) -
--     only meaningful for a classical per-region OCR pipeline; v1 uses a
--     single vision-LLM call instead.

BEGIN;

CREATE TABLE card_games (
    id SERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,          -- apitcg's tcg id, e.g. 'pokemon', 'one-piece'
    name TEXT NOT NULL,
    logo_image_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE card_series (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES card_games(id) ON DELETE RESTRICT,
    external_id TEXT,                   -- apitcg's serie id
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (game_id, name)
);

CREATE TABLE card_sets (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES card_games(id) ON DELETE RESTRICT,
    series_id INTEGER REFERENCES card_series(id) ON DELETE SET NULL,
    external_id TEXT,                   -- apitcg's set id
    name TEXT NOT NULL,
    set_code TEXT,
    printed_total INTEGER,
    total_cards INTEGER,
    release_date DATE,
    symbol_image_url TEXT,
    logo_image_url TEXT,
    language TEXT NOT NULL DEFAULT 'English',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (game_id, name, language)
);

CREATE TABLE trading_cards (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES card_games(id) ON DELETE RESTRICT,
    set_id INTEGER NOT NULL REFERENCES card_sets(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    card_number TEXT,
    code TEXT,                          -- combined code, e.g. 'OP03-070'
    rarity TEXT,
    language TEXT NOT NULL DEFAULT 'English',
    description TEXT,
    -- Per-game stat bag: HP/attacks/Power/Color for Pokemon, mana cost/type
    -- line for Magic, etc. Mirrors apitcg's own `attributes` field - do not
    -- add fixed columns per game here.
    attributes JSONB,
    image_small TEXT,
    image_medium TEXT,
    image_large TEXT,
    -- Resolved from owners' personal photos, same role as Comic.master_photo.
    master_photo TEXT,
    average_price NUMERIC(12,2),
    release_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (set_id, card_number, language)
);

CREATE TABLE trading_card_variants (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES trading_cards(id) ON DELETE CASCADE,
    variant_type TEXT NOT NULL,
    finish TEXT,
    foil_pattern TEXT,
    parallel_type TEXT,
    stamp TEXT,
    stamped_text TEXT,
    alternate_art BOOLEAN NOT NULL DEFAULT FALSE,
    special_print BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (
        card_id, variant_type, finish, foil_pattern,
        parallel_type, stamp, stamped_text
    )
);

CREATE TABLE trading_card_external_ids (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES trading_cards(id) ON DELETE CASCADE,
    source TEXT NOT NULL,               -- 'apitcg', 'tcgplayer', ...
    external_id TEXT NOT NULL,
    url TEXT,
    UNIQUE (source, external_id)
);

CREATE TABLE trading_card_images (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES trading_cards(id) ON DELETE CASCADE,
    variant_id INTEGER REFERENCES trading_card_variants(id) ON DELETE CASCADE,
    image_type TEXT NOT NULL,           -- front / back / reference / variant / scan
    image_url TEXT NOT NULL,
    image_hash TEXT,
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE trading_card_prices (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES trading_cards(id) ON DELETE CASCADE,
    variant_id INTEGER REFERENCES trading_card_variants(id) ON DELETE CASCADE,
    source TEXT NOT NULL,               -- 'apitcg:tcgplayer', 'apitcg:tcgmatch', ...
    price_type TEXT NOT NULL,
    condition TEXT,
    grader TEXT,
    grade TEXT,
    price NUMERIC(12,2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE trading_card_price_history (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES trading_cards(id) ON DELETE CASCADE,
    variant_id INTEGER REFERENCES trading_card_variants(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    condition TEXT,
    grader TEXT,
    grade TEXT,
    price NUMERIC(12,2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Phase 2 / optional - not needed for v1.
CREATE TABLE storage_locations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    location_type TEXT,
    parent_location_id INTEGER REFERENCES storage_locations(id) ON DELETE SET NULL,
    description TEXT,
    UNIQUE (name, parent_location_id)
);

-- Personal ownership - mirrors UserComic.
CREATE TABLE user_trading_cards (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES trading_cards(id) ON DELETE RESTRICT,
    variant_id INTEGER REFERENCES trading_card_variants(id) ON DELETE SET NULL,
    count INTEGER NOT NULL DEFAULT 1,
    condition TEXT NOT NULL DEFAULT 'Unknown',
    language TEXT,
    storage_location_id INTEGER REFERENCES storage_locations(id) ON DELETE SET NULL,
    storage_position TEXT,
    point_of_purchase TEXT,
    buy_date DATE,
    paid_price NUMERIC(12,2),
    asking_price NUMERIC(12,2),
    for_sale BOOLEAN NOT NULL DEFAULT FALSE,
    personal_img TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE card_grades (
    id SERIAL PRIMARY KEY,
    user_trading_card_id INTEGER NOT NULL REFERENCES user_trading_cards(id) ON DELETE CASCADE,
    grader TEXT NOT NULL,               -- PSA / BGS / SGC / CGC / ...
    grade TEXT NOT NULL,
    certification_number TEXT,
    graded_date DATE,
    label_type TEXT,
    population INTEGER,
    notes TEXT,
    UNIQUE (grader, certification_number)
);

CREATE TABLE card_transactions (
    id SERIAL PRIMARY KEY,
    user_trading_card_id INTEGER REFERENCES user_trading_cards(id) ON DELETE SET NULL,
    transaction_type TEXT NOT NULL,     -- Purchase / Sale / Trade / Gift / Other
    transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    source TEXT,
    counterparty TEXT,
    price NUMERIC(12,2),
    shipping NUMERIC(12,2) DEFAULT 0,
    tax NUMERIC(12,2) DEFAULT 0,
    fees NUMERIC(12,2) DEFAULT 0,
    total_cost NUMERIC(12,2),
    notes TEXT
);

-- Mirrors CollectionSnapshot - portfolio value over time, distinct from
-- trading_card_price_history (market price over time per card).
CREATE TABLE card_collection_snapshots (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    card_count INTEGER NOT NULL DEFAULT 0,
    total_paid NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_value NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, date)
);

-- Identification pipeline (v1: single vision-LLM call, not classical OCR).
CREATE TABLE identification_scans (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    processed_image_url TEXT,
    raw_response JSONB,                 -- vision-LLM's structured output
    detected_name TEXT,
    detected_number TEXT,
    detected_set TEXT,
    detected_language TEXT,
    detected_variant TEXT,
    detected_game_id INTEGER REFERENCES card_games(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE identification_matches (
    id SERIAL PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES identification_scans(id) ON DELETE CASCADE,
    candidate_card_id INTEGER NOT NULL REFERENCES trading_cards(id) ON DELETE CASCADE,
    candidate_variant_id INTEGER REFERENCES trading_card_variants(id) ON DELETE CASCADE,
    confidence NUMERIC(5,4),
    match_method TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scan_id, candidate_card_id, candidate_variant_id)
);

CREATE INDEX idx_trading_cards_name ON trading_cards(name);
CREATE INDEX idx_trading_cards_number ON trading_cards(card_number);
CREATE INDEX idx_trading_cards_set ON trading_cards(set_id);
CREATE INDEX idx_trading_cards_game ON trading_cards(game_id);
CREATE INDEX idx_trading_card_variants_card ON trading_card_variants(card_id);
CREATE INDEX idx_user_trading_cards_card ON user_trading_cards(card_id);
CREATE INDEX idx_user_trading_cards_user ON user_trading_cards(user_id);
CREATE INDEX idx_user_trading_cards_storage ON user_trading_cards(storage_location_id);
CREATE INDEX idx_trading_card_prices_card ON trading_card_prices(card_id);
CREATE INDEX idx_price_history_card_date ON trading_card_price_history(card_id, recorded_at DESC);
CREATE INDEX idx_external_ids ON trading_card_external_ids(source, external_id);
CREATE INDEX idx_scans_detected_number ON identification_scans(detected_number);
CREATE INDEX idx_scans_detected_name ON identification_scans(detected_name);
CREATE INDEX idx_matches_scan_confidence ON identification_matches(scan_id, confidence DESC);

COMMIT;
