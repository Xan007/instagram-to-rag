import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from config.paths import CONFIG_DIR

PROFILES_DIR = CONFIG_DIR / "profiles"


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
