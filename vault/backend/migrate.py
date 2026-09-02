"""
Idempotent schema migration script.
Run before starting the server when the database already exists.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import crud, crud_cards
from app.auth import hash_password
from app.database import Base
from app.models import User
import app.models  # noqa: F401 - ensures all models are registered on Base.metadata

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://comicvault:comicvault@localhost:5432/comicvault")
engine = create_engine(DATABASE_URL)

MIGRATIONS = [
    # Add is_kiosk column to users
    """
    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_kiosk BOOLEAN NOT NULL DEFAULT FALSE
    """,

    # Create sales table
    """
    CREATE TABLE IF NOT EXISTS sales (
        id          SERIAL PRIMARY KEY,
        user_comic_id INTEGER NOT NULL
            REFERENCES user_comics(id) ON DELETE CASCADE,
        sell_date   TIMESTAMP NOT NULL,
        sell_price  FLOAT,
        notes       TEXT,
        created_at  TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS ix_sales_user_comic_id ON sales(user_comic_id)
    """,

    # Migrate existing sell_date values on user_comics into Sale rows, then drop the column
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'user_comics' AND column_name = 'sell_date'
        ) THEN
            INSERT INTO sales (user_comic_id, sell_date, created_at)
            SELECT id, sell_date, NOW()
            FROM user_comics
            WHERE sell_date IS NOT NULL;

            ALTER TABLE user_comics DROP COLUMN sell_date;
        END IF;
    END $$
    """,

    # Add personal_img column to user_comics (added after some deployments' last
    # full rebuild, so create_all alone won't add it to an existing table)
    """
    ALTER TABLE user_comics
        ADD COLUMN IF NOT EXISTS personal_img VARCHAR
    """,

    # Add asking_price column to user_comics
    """
    ALTER TABLE user_comics
        ADD COLUMN IF NOT EXISTS asking_price FLOAT
    """,

    # Add master_photo column to comics
    """
    ALTER TABLE comics
        ADD COLUMN IF NOT EXISTS master_photo VARCHAR
    """,

    # Drop the plain artist column (superseded by cover_artist)
    """
    ALTER TABLE comics
        DROP COLUMN IF EXISTS artist
    """,

    """
    ALTER TABLE external_issue_cache
        DROP COLUMN IF EXISTS artist
    """,

    # Add legacy_number column to comics
    """
    ALTER TABLE comics
        ADD COLUMN IF NOT EXISTS legacy_number VARCHAR
    """,

    # Add do_not_sell column to user_comics and user_trading_cards
    """
    ALTER TABLE user_comics
        ADD COLUMN IF NOT EXISTS do_not_sell BOOLEAN NOT NULL DEFAULT FALSE
    """,

    """
    ALTER TABLE user_trading_cards
        ADD COLUMN IF NOT EXISTS do_not_sell BOOLEAN NOT NULL DEFAULT FALSE
    """,

    # Add reserve_count column to user_comics and user_trading_cards - how
    # many of `count` are held back from being counted as available for sale.
    # Nullable (like `count` itself) rather than NOT NULL - a cleared number
    # input on the frontend sends null, not 0, and every read site already
    # treats null the same as 0 (`uc.reserve_count or 0`).
    """
    ALTER TABLE user_comics
        ADD COLUMN IF NOT EXISTS reserve_count INTEGER DEFAULT 0
    """,

    """
    ALTER TABLE user_trading_cards
        ADD COLUMN IF NOT EXISTS reserve_count INTEGER DEFAULT 0
    """,

    # Rename comics.direct -> comics.newstand, inverting its meaning: the old
    # column meant "is this a direct-market copy" (True = direct), CSV header
    # "newstand/direct"; the new one means "is this a newsstand copy" (True =
    # newsstand, the rarer case) with a plain "Newstand" CSV header - so
    # existing True/False values must flip, not just get relabeled. Guarded on
    # the old column still existing so this only ever runs once.
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'comics' AND column_name = 'direct'
        ) THEN
            UPDATE comics SET direct = NOT direct WHERE direct IS NOT NULL;
            ALTER TABLE comics RENAME COLUMN direct TO newstand;
        END IF;
    END $$
    """,

    # Same rename on external_issue_cache - always NULL there (GCD never
    # supplies this field, see gcd_lookup.ENRICHABLE_FIELDS), so no invert
    # needed, just keeping the column name consistent with comics.newstand.
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'external_issue_cache' AND column_name = 'direct'
        ) THEN
            ALTER TABLE external_issue_cache RENAME COLUMN direct TO newstand;
        END IF;
    END $$
    """,

    # Add cover_letter column to comics and external_issue_cache - the short
    # cover designation (e.g. "A", "B", "1"), distinct from `variant`'s
    # free-text description. No lookup provider currently supplies this.
    """
    ALTER TABLE comics
        ADD COLUMN IF NOT EXISTS cover_letter VARCHAR
    """,

    """
    ALTER TABLE external_issue_cache
        ADD COLUMN IF NOT EXISTS cover_letter VARCHAR
    """,

    # Admin-configurable count of items shown in each kiosk featured
    # section (Today's Picks / Signed / cards Today's Picks / Graded),
    # replacing the hardcoded FEATURED_LIMIT constant in routes/kiosk.py.
    """
    ALTER TABLE kiosk_settings
        ADD COLUMN IF NOT EXISTS featured_limit INTEGER NOT NULL DEFAULT 25
    """,

    # Seller (default) vs. Collector user profile - Collector hides sales
    # and pricing tools throughout the app. Existing accounts default to
    # Seller so nothing changes for them.
    """
    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_collector BOOLEAN NOT NULL DEFAULT FALSE
    """,

    # "Anything you looking for in particular?" on the kiosk signup form.
    """
    ALTER TABLE kiosk_signups
        ADD COLUMN IF NOT EXISTS notes TEXT
    """,

    # Google sign-in (see routes/users.py's /auth/google-login): an account
    # can now exist with no password at all, and is matched to a Google
    # login by email.
    """
    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS email VARCHAR UNIQUE
    """,
    """
    ALTER TABLE users
        ALTER COLUMN password_hash DROP NOT NULL
    """,

    # Welcome tour (DashboardPage.tsx's WelcomeTourModal) - DEFAULT TRUE
    # backfills every pre-existing account so the tour only ever shows for
    # a genuinely new signup (crud.create_user/create_google_user override
    # this to False explicitly).
    """
    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS has_seen_tour BOOLEAN NOT NULL DEFAULT TRUE
    """,

    # Admin "suspend user" action (AdminPage.tsx) - see auth.py's
    # _get_user_from_token for the login-block + forced-logout behavior.
    """
    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN NOT NULL DEFAULT FALSE
    """,
]


def seed_kiosk_user():
    with Session(engine) as session:
        existing = session.query(User).filter(User.username == "kiosk").first()
        if existing:
            return
        kiosk_password = os.getenv("KIOSK_PASSWORD", "kiosk")
        session.add(User(
            username="kiosk",
            password_hash=hash_password(kiosk_password),
            is_admin=False,
            is_kiosk=True,
        ))
        session.commit()
    print("Kiosk user ensured.")


def promote_shop_account_admin():
    """Ensures the shop's own account (crud.MASTER_PHOTO_OWNER_USERNAME,
    currently "digitalgiant") is an admin. No-op if that account doesn't
    exist yet (e.g. before it's signed up) or is already an admin."""
    with Session(engine) as session:
        user = session.query(User).filter(User.username == crud.MASTER_PHOTO_OWNER_USERNAME).first()
        if user and not user.is_admin:
            user.is_admin = True
            session.commit()
    print("Shop account admin status ensured.")


def backfill_master_photos():
    with Session(engine) as session:
        crud.backfill_master_photos(session)
    print("Master photos backfilled.")


def backfill_card_master_photos():
    with Session(engine) as session:
        crud_cards.backfill_card_master_photos(session)
    print("Card master photos backfilled.")


def run():
    # Runs before the raw-SQL migrations below so tables/columns from the current
    # models.py exist on a fresh database (migrate.py runs before uvicorn/main.py's
    # own create_all, so a brand-new DB has no tables yet at this point).
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        for sql in MIGRATIONS:
            conn.execute(text(sql.strip()))
        conn.commit()
    print("Migrations applied.")

    seed_kiosk_user()
    promote_shop_account_admin()
    backfill_master_photos()
    backfill_card_master_photos()


if __name__ == "__main__":
    run()
