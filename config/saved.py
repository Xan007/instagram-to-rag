import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config.paths import SAVED_DIR

SAVED_POSTS_FILE = SAVED_DIR / "saved_posts.json"
STATE_FILE = SAVED_DIR / "state.json"

_URL_SHORTCODE_RE = re.compile(r"/(?:p|reel|tv|stories)/([A-Za-z0-9_-]+)")


class SavedState:
    total: int = 0
    imported_at: str = ""
    source: str = ""
    processed_ids: List[str] = None
    failed_ids: List[str] = None

    def __init__(self, **kwargs):
        self.total = kwargs.get("total", 0)
        self.imported_at = kwargs.get("imported_at", "")
        self.source = kwargs.get("source", "")
        self.processed_ids = kwargs.get("processed_ids", [])
        self.failed_ids = kwargs.get("failed_ids", [])

    def to_dict(self):
        data = self.__dict__.copy()
        data["processed_ids"] = list(data["processed_ids"])
        data["failed_ids"] = list(data["failed_ids"])
        return data


def _ensure_dir() -> None:
    SAVED_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> SavedState:
    if not STATE_FILE.exists():
        return SavedState()
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return SavedState(**json.load(f))


def save_state(state: SavedState) -> None:
    _ensure_dir()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=4)


def _extract_saved_posts_json_from_zip(zip_path: Path) -> bytes:
    with zipfile.ZipFile(zip_path) as zf:
        candidates = [
            n
            for n in zf.namelist()
            if n.replace("\\", "/").endswith("saved_posts.json")
        ]
        if not candidates:
            raise ValueError("No saved_posts.json found inside the zip export.")
        name = next(
            (n for n in candidates if "saved/saved_posts.json" in n.replace("\\", "/")),
            candidates[0],
        )
        return zf.read(name)


def import_saved_posts(path: Path) -> SavedState:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    source = str(path)
    if path.suffix.lower() == ".zip":
        raw = _extract_saved_posts_json_from_zip(path)
        source = f"{path.name} -> your_instagram_activity/saved/saved_posts.json"
    else:
        raw = path.read_bytes()

    data = json.loads(raw.decode("utf-8"))
    items = parse_saved_posts(data)

    _ensure_dir()
    SAVED_POSTS_FILE.write_bytes(raw)

    state = load_state()
    state.total = len(items)
    state.imported_at = datetime.now().isoformat(timespec="seconds")
    state.source = source
    save_state(state)
    return state


def parse_saved_posts(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        data = data.get("saved_posts") or data.get("saved_collections") or []
    if not isinstance(data, list):
        raise ValueError("Unrecognized saved_posts.json format.")

    posts: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "label_values" in item:
            labels = {}
            for lv in item.get("label_values", []):
                if "label" in lv:
                    labels[str(lv["label"]).lower()] = lv.get("value", "")
            url = labels.get("url", "")
            caption = labels.get("pie de foto", "") or labels.get("caption", "")
            title = labels.get("título", "") or labels.get("titulo", "") or labels.get("title", "")
        else:
            url = item.get("url", "")
            caption = item.get("caption", "")
            title = item.get("title", "")

        m = _URL_SHORTCODE_RE.search(str(url))
        post_id = m.group(1) if m else None
        if not post_id:
            continue
        posts.append(
            {
                "id": post_id,
                "url": url,
                "caption": caption,
                "title": title,
                "timestamp": item.get("timestamp", 0),
            }
        )
    return posts