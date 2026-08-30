"""Repository layer for database operations."""
from typing import List, Optional

from sqlalchemy.orm import Session

from storage.models import Profile, SavedPost, SavedState, Setting


# ── Settings ──────────────────────────────────────────────────────────────

def get_setting(db: Session, key: str) -> Optional[dict]:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else None


def set_setting(db: Session, key: str, value: dict) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


def get_all_settings(db: Session) -> dict:
    rows = db.query(Setting).all()
    return {row.key: row.value for row in rows}


# ── Profiles ──────────────────────────────────────────────────────────────

def get_profile(db: Session, username: str) -> Optional[Profile]:
    return db.query(Profile).filter(Profile.username == username).first()


def list_profiles(db: Session) -> List[Profile]:
    return db.query(Profile).all()


def upsert_profile(db: Session, profile: Profile) -> Profile:
    existing = get_profile(db, profile.username)
    if existing:
        existing.interests = profile.interests
        existing.max_posts = profile.max_posts
        existing.analysis_mode = profile.analysis_mode
        existing.audio_only = profile.audio_only
        existing.processed_ids = profile.processed_ids
        existing.failed_ids = profile.failed_ids
        db.commit()
        db.refresh(existing)
        return existing
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, username: str) -> bool:
    profile = get_profile(db, username)
    if not profile:
        return False
    db.delete(profile)
    db.commit()
    return True


# ── Saved Posts ───────────────────────────────────────────────────────────

def get_saved_post(db: Session, post_id: str) -> Optional[SavedPost]:
    return db.query(SavedPost).filter(SavedPost.id == post_id).first()


def list_saved_posts(db: Session) -> List[SavedPost]:
    return db.query(SavedPost).all()


def upsert_saved_posts_bulk(db: Session, posts: List[SavedPost]) -> None:
    """Bulk insert or update saved posts."""
    for post in posts:
        existing = get_saved_post(db, post.id)
        if not existing:
            db.add(post)
    db.commit()


def get_saved_state(db: Session) -> SavedState:
    state = db.query(SavedState).filter(SavedState.id == 1).first()
    if not state:
        state = SavedState(id=1)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def save_saved_state(db: Session, state: SavedState) -> None:
    db.commit()
