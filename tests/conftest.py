"""Redirect all project state to temp dirs BEFORE any project import,
so tests never touch the real ~/.instarag or ./data of the user."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="instarag_tests_")
os.environ["INSTARAG_CONFIG_DIR"] = os.path.join(_TMP, "config")
os.environ["INSTARAG_DATA_DIR"] = os.path.join(_TMP, "data")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
