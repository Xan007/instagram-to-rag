from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import zipfile

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
    import storage.repositories as repo
    return repo


def _db():
    from storage.db import get_session
    return get_session()


def load_state(user_id: str = "default") -> SavedState:
    db = _db()
    try:
        model = _repo().get_user_saved_state(db, user_id)
        return SavedState(
            total=model.total or 0,
            imported_at=model.imported_at or "",
            source=model.source or "",
            processed_ids=list(model.processed_ids or []),
            failed_ids=list(model.failed_ids or []),
        )
    finally:
        db.close()


def save_state(state: SavedState, user_id: str = "default") -> None:
    db = _db()
    try:
        model = _repo().get_user_saved_state(db, user_id)
        model.total = state.total
        model.imported_at = state.imported_at
        model.source = state.source
        model.processed_ids = list(state.processed_ids or [])
        model.failed_ids = list(state.failed_ids or [])
        _repo().save_user_saved_state(db, model)
    finally:
        db.close()


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


def import_saved_posts(path: Path, user_id: str = "default") -> SavedState:
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

    from storage.models import Post, UserSavedPost
    db = _db()
    try:
        for item in items:
            post_id = item["id"]
            existing = _repo().get_post(db, post_id)
            if not existing:
                desc = (item.get("title", "") + "\n" + item.get("caption", "")).strip()
                post_type = "Reel" if "/reel/" in item.get("url", "") else "Post"
                _repo().upsert_post(
                    db,
                    Post(
                        id=post_id,
                        url=item.get("url", ""),
                        creator_username="",
                        type=post_type,
                        description=desc,
                    ),
                )
            _repo().add_user_saved_post(db, user_id, post_id, source_url=item.get("url", ""))

        state = _repo().get_user_saved_state(db, user_id)
        state.total = _repo().count_user_saved_posts(db, user_id)
        state.imported_at = datetime.now(timezone.utc).isoformat()
        state.source = source
        _repo().save_user_saved_state(db, state)

        return SavedState(
            total=state.total,
            imported_at=state.imported_at,
            source=state.source,
            processed_ids=list(state.processed_ids or []),
            failed_ids=list(state.failed_ids or []),
        )
    finally:
        db.close()


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
                if isinstance(lv, dict) and "label" in lv:
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

