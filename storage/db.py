"""Database engine and session management."""
import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_engine = None
_SessionLocal = None
_current_url = None


def _get_database_url() -> str:
    """Get database URL from env or default to SQLite."""
    from config.paths import CONFIG_DIR
    default_db = CONFIG_DIR / "instarag.db"
    return os.getenv("INSTARAG_DATABASE_URL", f"sqlite:///{default_db}")


def get_engine():
    """Get or create the SQLAlchemy engine (singleton, resets if URL changes)."""
    global _engine, _current_url
    url = _get_database_url()
    # Reset engine if URL changed (important for tests with in-memory SQLite)
    if _engine is None or url != _current_url:
        _current_url = url
        connect_args = {}
        engine_kwargs = {}
        # SQLite needs check_same_thread=False for FastAPI
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            # In-memory SQLite: use StaticPool so all connections share the same DB
            if url == "sqlite://" or url == "sqlite:///:memory:":
                engine_kwargs["poolclass"] = StaticPool
            else:
                # Ensure parent directory exists for file-based SQLite
                db_path = url.replace("sqlite:///", "")
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args=connect_args, **engine_kwargs)
        global _SessionLocal
        _SessionLocal = None
    return _engine


def _get_session_factory():
    """Get or create the session factory (singleton)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def _migrate_profiles_table(engine) -> None:
    """Add new columns to the profiles table for existing SQLite databases.

    SQLite does not support ALTER TABLE ... ADD COLUMN IF NOT EXISTS, so we
    probe the column list and only run the statement when the column is missing.
    """
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return  # Non-SQLite DBs rely on Alembic / proper migrations

    with engine.connect() as conn:
        cols_result = conn.execute(text("PRAGMA table_info(profiles)"))
        existing_cols = {row[1] for row in cols_result}

        new_cols = {
            "last_scraped_at": "FLOAT",
            "last_run_at": "VARCHAR",
        }
        for col_name, col_type in new_cols.items():
            if col_name not in existing_cols:
                conn.execute(
                    text(f"ALTER TABLE profiles ADD COLUMN {col_name} {col_type}")
                )
        conn.commit()


def init_db() -> None:
    """Create all tables and apply lightweight inline migrations."""
    from storage.models import Base
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _migrate_profiles_table(engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    SessionLocal = _get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """Get a raw session (for non-FastAPI usage like CLI)."""
    SessionLocal = _get_session_factory()
    return SessionLocal()
