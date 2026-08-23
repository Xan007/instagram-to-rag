import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def load_runtime_env() -> None:
    """Load .env files for source and frozen executable modes.

    Precedence (highest first):
    1) Existing process environment variables.
    2) .env next to the executable (when running frozen).
    3) .env in the current working directory.
    4) ~/.instarag/.env (per-user persistent config).
    """
    candidates = []

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")

    candidates.extend([Path.cwd() / ".env", Path.home() / ".instarag" / ".env"])

    for env_path in candidates:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
