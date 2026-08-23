import os
from pathlib import Path

CONFIG_DIR = Path(os.getenv("INSTARAG_CONFIG_DIR", Path.home() / ".instarag"))
DATA_DIR = Path(os.getenv("INSTARAG_DATA_DIR", "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAVED_DIR = DATA_DIR / "saved"
