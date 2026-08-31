"""Global Instagram profile config helpers.

IGProfiles are scraped once and shared across all users.
There are no per-user interests here — interests live at the Group level.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class IGProfileInfo:
    username: str
    last_scraped_at: Optional[float] = None
    last_run_at: Optional[str] = None
    total_posts_scraped: int = 0


def _repo():
    import storage.repositories as repo
    return repo


def _db():
    from storage.db import get_session
    return get_session()


def _from_model(model) -> IGProfileInfo:
    return IGProfileInfo(
        username=model.username,
        last_scraped_at=getattr(model, "last_scraped_at", None),
        last_run_at=getattr(model, "last_run_at", None),
        total_posts_scraped=getattr(model, "total_posts_scraped", 0) or 0,
    )


def load_ig_profile(username: str) -> Optional[IGProfileInfo]:
    db = _db()
    try:
        model = _repo().get_ig_profile(db, username)
        return _from_model(model) if model else None
    finally:
        db.close()


def save_ig_profile(profile: IGProfileInfo) -> None:
    from storage.models import IGProfile
    db = _db()
    try:
        model = IGProfile(
            username=profile.username,
            last_scraped_at=profile.last_scraped_at,
            last_run_at=profile.last_run_at,
            total_posts_scraped=profile.total_posts_scraped,
        )
        _repo().upsert_ig_profile(db, model)
    finally:
        db.close()


def list_ig_profiles() -> List[IGProfileInfo]:
    db = _db()
    try:
        return [_from_model(m) for m in _repo().list_ig_profiles(db)]
    finally:
        db.close()


def delete_ig_profile(username: str) -> bool:
    db = _db()
    try:
        return _repo().delete_ig_profile(db, username)
    finally:
        db.close()
