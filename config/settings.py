import json
from pathlib import Path
from pydantic import BaseModel, Field

CONFIG_DIR = Path.home() / ".ig_profile_to_rag"
CONFIG_FILE = CONFIG_DIR / "settings.json"

class AppSettings(BaseModel):
    audio_only: bool = Field(default=False, description="Whether to only process audio globally")
    engine: str = Field(default="gemini", description="Engine to use: 'gemini' or 'local_whisper'")
    embed_provider: str = Field(default="gemini", description="Embedding provider: 'gemini' or 'local'")
    ig_username: str = Field(default="", description="Your Instagram username (used for authenticated scraping to avoid 429 errors)")
    scraper_engine: str = Field(default="apify", description="Scraper engine to use: 'apify' or 'instaloader'")

def load_settings() -> AppSettings:
    """Load settings from the configuration file."""
    if not CONFIG_FILE.exists():
        return AppSettings()
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return AppSettings(**data)

def save_settings(settings: AppSettings) -> None:
    """Save settings to the configuration file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, indent=4)
