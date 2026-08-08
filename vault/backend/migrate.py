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
