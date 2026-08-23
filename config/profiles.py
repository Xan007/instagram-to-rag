import json
from pathlib import Path
from typing import List, Optional

from config.paths import CONFIG_DIR

PROFILES_DIR = CONFIG_DIR / "profiles"

class ProfileConfig:
    username: str
    interests: str = ""
    max_posts: int = 50
    processed_ids: List[str] = None
    analysis_mode: str = "gemini"
    audio_only: bool = False
    failed_ids: List[str] = None

    def __init__(self, **kwargs):
        self.username = kwargs.get("username", "")
        self.interests = kwargs.get("interests", "")
        self.max_posts = kwargs.get("max_posts", 50)
        self.processed_ids = kwargs.get("processed_ids", [])
        self.analysis_mode = kwargs.get("analysis_mode", "gemini")
        self.audio_only = kwargs.get("audio_only", False)
        self.failed_ids = kwargs.get("failed_ids", [])

    def to_dict(self):
        data = self.__dict__.copy()
        data["processed_ids"] = list(data["processed_ids"])
        data["failed_ids"] = list(data["failed_ids"])
        return data

def _get_profile_path(username: str) -> Path:
    return PROFILES_DIR / f"{username}.json"

def load_profile(username: str) -> Optional[ProfileConfig]:
    path = _get_profile_path(username)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ProfileConfig(**data)

def save_profile(profile: ProfileConfig) -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = _get_profile_path(profile.username)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, indent=4, ensure_ascii=False)

def list_profiles() -> List[str]:
    if not PROFILES_DIR.exists():
        return []
    return [f.stem for f in PROFILES_DIR.glob("*.json")]

def delete_profile(username: str) -> bool:
    path = _get_profile_path(username)
    if not path.exists():
        return False
    path.unlink()
    return True
