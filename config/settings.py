import json

from config.paths import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / "settings.json"

class AppSettings:
    audio_only: bool = False
    engine: str = "gemini"
    embed_provider: str = "gemini"

    @classmethod
    def from_dict(cls, data: dict):
        obj = cls()
        obj.__dict__.update({k: v for k, v in data.items() if hasattr(obj, k)})
        return obj

def load_settings():
    if not CONFIG_FILE.exists():
        return AppSettings()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return AppSettings.from_dict(json.load(f))

def save_settings(settings) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.__dict__, f, indent=4)
