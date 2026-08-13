from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Separate database, separate engine/session from app.database - these tables
# live in gcd-modifier's own `gcd` database on the same Postgres server, not
# in `comicvault`. Read-only: nothing in this app ever writes here, and the
# tables already exist (created/loaded by gcd-modifier), so there's no
# metadata.create_all() call - see app.gcd_models for the model definitions.
_engine = create_engine(settings.gcd_database_url) if settings.gcd_database_url else None
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine) if _engine else None


def get_gcd_db():
    """Yields a session for the gcd database, or None if GCD_DATABASE_URL
    isn't configured. Every call site treats None the same as "no match" and
    falls through to the existing Metron/ComicVine lookup path."""
    if _SessionLocal is None:
        yield None
        return
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
