from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class ProfileConfig:
    username: str = ""
    interests: str = ""
    max_posts: int = 50
    processed_ids: List[str] = field(default_factory=list)
    analysis_mode: str = "gemini"
    audio_only: bool = False
    failed_ids: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _repo():
    """Lazy import to avoid creating engine at module load time."""
    import storage.repositories as repo
    return repo


def _db():
    from storage.db import get_session
    return get_session()


def _to_model(profile: ProfileConfig):
    from storage.models import Profile
    return Profile(
        username=profile.username,
        interests=profile.interests,
        max_posts=profile.max_posts,
        processed_ids=profile.processed_ids,
        analysis_mode=profile.analysis_mode,
        audio_only=profile.audio_only,
        failed_ids=profile.failed_ids,
    )


def _from_model(model) -> ProfileConfig:
    return ProfileConfig(
        username=model.username,
        interests=model.interests or "",
        max_posts=model.max_posts or 50,
        processed_ids=model.processed_ids or [],
        analysis_mode=model.analysis_mode or "gemini",
        audio_only=model.audio_only or False,
        failed_ids=model.failed_ids or [],
    )


def load_profile(username: str) -> Optional[ProfileConfig]:
    db = _db()
    try:
        model = _repo().get_profile(db, username)
        return _from_model(model) if model else None
    finally:
        db.close()


def save_profile(profile: ProfileConfig) -> None:
    db = _db()
    try:
        model = _to_model(profile)
        _repo().upsert_profile(db, model)
    finally:
        db.close()


def list_profiles() -> List[str]:
    db = _db()
    try:
        return [p.username for p in _repo().list_profiles(db)]
    finally:
        db.close()


def delete_profile(username: str) -> bool:
    db = _db()
    try:
        return _repo().delete_profile(db, username)
    finally:
        db.close()
