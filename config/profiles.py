import json
from pathlib import Path
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

PROFILES_DIR = Path.home() / ".ig_profile_to_rag" / "profiles"

class ProfileConfig(BaseModel):
    username: str
    interests: str = Field(default="", description="Comma-separated list of interests for this profile")
    max_posts: int = Field(default=50, description="Maximum number of posts to process per run")
    processed_ids: List[str] = Field(default_factory=list, description="List of post IDs that have already processed")
    # New fields for flexible analysis
    analysis_mode: str = Field(default="gemini", description="'gemini' | 'local_whisper' | 'openai_whisper'")
    audio_only: bool = Field(default=False, description="If true, only audio (transcription) is processed, skipping visual analysis")
    failed_ids: List[str] = Field(default_factory=list, description="Post IDs that failed processing, for retry later")


def _get_profile_path(username: str) -> Path:
    return PROFILES_DIR / f"{username}.json"

def load_profile(username: str) -> Optional[ProfileConfig]:
    """Load a specific profile configuration."""
    path = _get_profile_path(username)
    if not path.exists():
        return None
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return ProfileConfig(**data)

def save_profile(profile: ProfileConfig) -> None:
    """Save a profile configuration, creating directories if needed."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = _get_profile_path(profile.username)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(), f, indent=4)

def list_profiles() -> List[str]:
    """List all configured profile usernames."""
    if not PROFILES_DIR.exists():
        return []
    return [f.stem for f in PROFILES_DIR.glob("*.json")]

def delete_profile(username: str) -> bool:
    """Delete a profile file. Returns True if deleted, False if it did not exist."""
    path = _get_profile_path(username)
    if not path.exists():
        return False
    path.unlink()
    return True
