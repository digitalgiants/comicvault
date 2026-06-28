"""
Idempotent schema migration script.
Run before starting the server when the database already exists.
"""
import os
from sqlalchemy import create_engine, text

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
]


def run():
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            conn.execute(text(sql.strip()))
        conn.commit()
    print("Migrations applied.")


if __name__ == "__main__":
    run()
