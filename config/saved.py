from dataclasses import asdict, dataclass, field
from typing import List, Optional

from config.utils import URL_SHORTCODE_RE


@dataclass
class SavedState:
    total: int = 0
    imported_at: str = ""
    source: str = ""
    processed_ids: List[str] = field(default_factory=list)
    failed_ids: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _repo():
    """Lazy import to avoid creating engine at module load time."""
    import storage.repositories as repo
    return repo


def _db():
    from storage.db import get_session
    return get_session()


def load_state() -> SavedState:
    db = _db()
    try:
        model = _repo().get_saved_state(db)
        return SavedState(
            total=model.total or 0,
            imported_at=model.imported_at or "",
            source=model.source or "",
            processed_ids=model.processed_ids or [],
            failed_ids=model.failed_ids or [],
        )
    finally:
        db.close()


def save_state(state: SavedState) -> None:
    db = _db()
    try:
        model = _repo().get_saved_state(db)
        model.total = state.total
        model.imported_at = state.imported_at
        model.source = state.source
        model.processed_ids = state.processed_ids
        model.failed_ids = state.failed_ids
        _repo().save_saved_state(db, model)
    finally:
        db.close()


def _extract_saved_posts_json_from_zip(zip_path):
    import zipfile
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


def import_saved_posts(path) -> SavedState:
    import json
    from datetime import datetime
    from pathlib import Path

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

    from storage.models import SavedPost
    db = _db()
    try:
        models = [
            SavedPost(
                id=item["id"],
                url=item["url"],
                caption=item["caption"],
                title=item["title"],
                timestamp=item.get("timestamp", 0),
            )
            for item in items
        ]
        _repo().upsert_saved_posts_bulk(db, models)

        state = _repo().get_saved_state(db)
        state.total = len(items)
        state.imported_at = datetime.now().isoformat(timespec="seconds")
        state.source = source
        _repo().save_saved_state(db, state)

        return SavedState(
            total=state.total,
            imported_at=state.imported_at,
            source=state.source,
            processed_ids=state.processed_ids or [],
            failed_ids=state.failed_ids or [],
        )
    finally:
        db.close()


def parse_saved_posts(data) -> List[dict]:
    import json as _json

    if isinstance(data, dict):
        data = data.get("saved_posts") or data.get("saved_collections") or []
    if not isinstance(data, list):
        raise ValueError("Unrecognized saved_posts.json format.")

    posts: List[dict] = []
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

        m = URL_SHORTCODE_RE.search(str(url))
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
