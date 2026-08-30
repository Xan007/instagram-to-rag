"""Process imported saved posts through the pipeline."""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from config.saved import load_state, parse_saved_posts, save_state
from config.profiles import list_profiles, load_profile
from storage.db import get_session
from storage.models import SavedPost
import storage.repositories as repo
from src.pipeline._common import Progress, download_with_ytdlp, echo


def _get_saved_posts_from_db() -> List[Dict[str, Any]]:
    """Get all saved posts from database as dicts."""
    db = get_session()
    try:
        posts = repo.list_saved_posts(db)
        return [
            {
                "id": p.id,
                "url": p.url,
                "caption": p.caption or "",
                "title": p.title or "",
                "timestamp": p.timestamp or 0,
            }
            for p in posts
        ]
    finally:
        db.close()


def process_saved(
    *,
    limit: Optional[int] = None,
    caption_only: bool = False,
    workers: int = 4,
    progress: Progress = echo,
) -> Dict[str, Any]:
    """Process ALL imported saved posts (no interest filter) and index their knowledge."""
    from src.analyzer.gemini_analyzer import GeminiAnalyzer
    from src.indexer.pinecone_indexer import PineconeIndexer

    items = _get_saved_posts_from_db()
    if not items:
        raise ValueError("No saved posts imported. Run 'saved import' first.")

    state = load_state()

    profile_ids: set = set()
    for username in list_profiles():
        p = load_profile(username)
        if p:
            profile_ids.update(p.processed_ids)

    saved_ids = set(state.processed_ids)
    pending = [it for it in items if it["id"] not in saved_ids and it["id"] not in profile_ids]
    already = [it for it in items if it["id"] in saved_ids or it["id"] in profile_ids]
    newly_known = [it for it in already if it["id"] not in saved_ids]
    for it in newly_known:
        state.processed_ids.append(it["id"])

    if limit is not None:
        pending = pending[:limit]

    progress(
        f"Total saved posts: {len(items)} | Already known (profiles/saved): {len(already)} | To process: {len(pending)}"
    )
    if newly_known:
        progress(f"Marked {len(newly_known)} posts as processed because they were already indexed via a profile.")

    if not pending:
        save_state(state)
        return {"processed": 0, "skipped": 0, "failed": 0, "total_processed": len(state.processed_ids)}

    try:
        analyzer = GeminiAnalyzer()
        indexer = PineconeIndexer()
    except ValueError as e:
        raise ValueError(f"Configuration Error: {e}. Check your .env for GEMINI_API_KEY, PINECONE_API_KEY, etc.")

    def process_item(item: Dict[str, Any]) -> Tuple[str, str, Optional[Exception]]:
        pid = item["id"]
        description = (item["title"] + "\n" + item["caption"]).strip()
        post = {
            "id": pid,
            "url": item["url"],
            "type": "Reel" if "/reel/" in item["url"] else "Post",
            "description": description,
            "media_items": [],
        }
        media_files: List[Dict[str, str]] = []
        try:
            if not caption_only:
                try:
                    media_files = download_with_ytdlp(item["url"], pid) or []
                except Exception as e:
                    progress(f"yt-dlp failed for {pid}: {e}")
                if not media_files:
                    progress(f"{pid}: no media available; will use caption if present.")

            if media_files:
                extracted_text = analyzer.extract_knowledge(media_files, description)
            else:
                if not description:
                    return "skipped", pid, None
                extracted_text = analyzer.extract_knowledge([], description)

            indexer.index_post("saved", post, extracted_text)
            return "ok", pid, None
        except Exception as e:
            return "failed", pid, e
        finally:
            for mf in media_files:
                if os.path.exists(mf["path"]):
                    os.remove(mf["path"])

    processed = 0
    failed = 0
    skipped = 0
    progress(f"Processing {len(pending)} posts with {workers} parallel workers (download + analysis)...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_item = {executor.submit(process_item, item): item for item in pending}
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            status, result_pid, error = future.result()
            if status == "ok":
                state.processed_ids.append(result_pid)
                if result_pid in state.failed_ids:
                    state.failed_ids.remove(result_pid)
                processed += 1
                progress(f"Extracted knowledge for {result_pid} | {item['url']}")
            elif status == "skipped":
                state.processed_ids.append(result_pid)
                if result_pid in state.failed_ids:
                    state.failed_ids.remove(result_pid)
                skipped += 1
                progress(f"Skipped {result_pid} (no caption/title and no media)")
            else:
                if result_pid not in state.failed_ids:
                    state.failed_ids.append(result_pid)
                failed += 1
                progress(f"Error analyzing saved post {result_pid}: {error}")
            save_state(state)

    return {
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "total_processed": len(state.processed_ids),
        "total_failed": len(state.failed_ids),
    }
