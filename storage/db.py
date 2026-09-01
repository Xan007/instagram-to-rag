import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_engine = None
_SessionLocal = None
_current_url = None


def _get_database_url() -> str:
    from config.paths import CONFIG_DIR
    default_db = CONFIG_DIR / "instarag.db"
    return os.getenv("INSTARAG_DATABASE_URL", f"sqlite:///{default_db}")


def get_engine():
    global _engine, _current_url, _SessionLocal
    url = _get_database_url()
    if _engine is None or url != _current_url:
        _current_url = url
        connect_args = {}
        engine_kwargs = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            if url in ("sqlite://", "sqlite:///:memory:"):
                engine_kwargs["poolclass"] = StaticPool
            else:
                db_path = url.replace("sqlite:///", "")
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args=connect_args, **engine_kwargs)
        _SessionLocal = None
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def _migrate(engine) -> None:
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return

    with engine.connect() as conn:
        def existing_cols(table: str):
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return {row[1] for row in rows}

        def add_col_if_missing(table: str, col: str, col_def: str):
            if col not in existing_cols(table):
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))

        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "ig_profiles" in tables:
            add_col_if_missing("ig_profiles", "total_posts_scraped", "INTEGER DEFAULT 0")
            add_col_if_missing("ig_profiles", "interests", "VARCHAR DEFAULT ''")
            add_col_if_missing("ig_profiles", "max_posts", "INTEGER DEFAULT 50")
            add_col_if_missing("ig_profiles", "processed_ids", "JSON DEFAULT '[]'")
            add_col_if_missing("ig_profiles", "failed_ids", "JSON DEFAULT '[]'")
            add_col_if_missing("ig_profiles", "analysis_mode", "VARCHAR DEFAULT 'gemini'")
            add_col_if_missing("ig_profiles", "audio_only", "BOOLEAN DEFAULT 0")

        if "user_saved_states" in tables:
            add_col_if_missing("user_saved_states", "processed_ids", "JSON DEFAULT '[]'")
            add_col_if_missing("user_saved_states", "failed_ids", "JSON DEFAULT '[]'")

        conn.commit()


def init_db() -> None:
    from storage.models import Base
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _migrate(engine)


def get_db() -> Generator[Session, None, None]:
    db = _get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    return _get_session_factory()()

