import json
from dataclasses import asdict, dataclass
from typing import get_type_hints

from config.paths import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / "settings.json"

VALID_ENGINES = {"gemini", "local_whisper"}
VALID_EMBED_PROVIDERS = {"gemini", "local"}
VALID_ANALYSIS_MODES = {"gemini", "local_whisper", "openai_whisper"}


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


def load_settings() -> AppSettings:
    if not CONFIG_FILE.exists():
        return AppSettings()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return AppSettings.from_dict(json.load(f))


def save_settings(settings: AppSettings) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(settings), f, indent=4)
