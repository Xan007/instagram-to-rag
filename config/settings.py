from dataclasses import asdict, dataclass
from typing import get_type_hints

VALID_ENGINES = {"gemini", "local_whisper"}
VALID_EMBED_PROVIDERS = {"gemini", "local"}
VALID_ANALYSIS_MODES = {"gemini", "local_whisper", "openai_whisper"}

SETTINGS_KEY = "app_settings"


@dataclass
class AppSettings:
    audio_only: bool = False
    engine: str = "gemini"
    embed_provider: str = "gemini"

    @classmethod
    def from_dict(cls, data: dict):
        hints = get_type_hints(cls)
        filtered = {k: v for k, v in data.items() if k in hints}
        return cls(**filtered)


def _repo():
    """Lazy import to avoid creating engine at module load time."""
    import storage.repositories as repo
    return repo


def _db():
    from storage.db import get_session
    return get_session()


def load_settings() -> AppSettings:
    db = _db()
    try:
        data = _repo().get_setting(db, SETTINGS_KEY)
        return AppSettings.from_dict(data) if data else AppSettings()
    finally:
        db.close()


def save_settings(settings: AppSettings) -> None:
    db = _db()
    try:
        _repo().set_setting(db, SETTINGS_KEY, asdict(settings))
    finally:
        db.close()
