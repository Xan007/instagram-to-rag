"""Global profile pipeline: scrape ALL posts → extract knowledge → index.

No interest filtering here. Interests apply at the Group level.
Deduplication: posts already in the `posts` table are skipped.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.ig_profiles import IGProfileInfo, load_ig_profile, save_ig_profile
from src.pipeline._common import Progress, echo


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def scrape_profile(
    username: str,
    *,
    newer_than: Optional[str] = None,
    max_posts: int = 200,
    analysis_mode: str = "gemini",
    keep_media: bool = False,
    progress: Progress = echo,
) -> Dict[str, Any]:
    """Scrape a global IG profile and index ALL posts (no interest filter).

    Posts already in the local DB are skipped (deduplication by post ID).
    Returns: processed, skipped_known, failed, total_indexed, last_scraped_at.
    """
    from src.scraper.apify_scraper import ApifyScraper
    from src.downloader.media_downloader import MediaDownloader
    from src.analyzer.gemini_analyzer import GeminiAnalyzer
    from src.indexer.pinecone_indexer import PineconeIndexer
    from storage.db import get_session
    import storage.repositories as repo

    run_start = time.time()
    run_iso = _now_iso()

    # Ensure profile exists in DB
    profile = load_ig_profile(username)
    if not profile:
        profile = IGProfileInfo(username=username)

    progress(f"[bold]Scraping @{username}[/bold] — {run_iso[:19]}Z")
    progress(
        f"  Mode: {analysis_mode} | Max posts: {max_posts}"
        + (f" | newer than: {newer_than}" if newer_than else "")
    )
    if profile.last_scraped_at:
        dt = datetime.fromtimestamp(profile.last_scraped_at, tz=timezone.utc)
        progress(f"  Last scraped: {dt.isoformat()[:19]}Z")

    # Fetch all already-indexed post IDs to skip them
    db = get_session()
    try:
        known_ids = set(repo.get_all_post_ids(db, creator_username=username))
    finally:
        db.close()

    progress(f"  Already indexed: {len(known_ids)} post(s) — will skip these.")

    # Update last_run_at immediately
    profile.last_run_at = run_iso
    save_ig_profile(profile)

    # Components
    try:
        scraper = ApifyScraper(only_posts_newer_than=newer_than)
        downloader = MediaDownloader()
        is_whisper = analysis_mode in ("local_whisper", "openai_whisper")
        if is_whisper:
            from src.analyzer.whisper_analyzer import WhisperAnalyzer
            analyzer = WhisperAnalyzer(mode=analysis_mode)
        else:
            analyzer = GeminiAnalyzer()
        indexer = PineconeIndexer()
    except ValueError as e:
        raise ValueError(f"Config error: {e}. Check .env for API keys.")

    new_post_ids: List[str] = []
    failed_ids: List[str] = []

    try:
        progress("Fetching post metadata from Apify…")
        all_posts: List[Dict[str, Any]] = list(
            scraper.get_posts_metadata(username, max_posts, list(known_ids))
        )
        progress(f"  Retrieved {len(all_posts)} new candidate(s).")

        if not all_posts:
            profile.last_scraped_at = run_start
            save_ig_profile(profile)
            return {
                "processed": 0,
                "skipped_known": len(known_ids),
                "failed": 0,
                "total_indexed": len(known_ids),
                "last_scraped_at": run_start,
                "message": "No new posts found — profile is up to date.",
            }

        def download_task(post: Dict[str, Any]):
            media_items = post.get("media_items", [])
            if is_whisper:
                video_urls = [m["url"] for m in media_items if m.get("type") == "video"]
                sources = [post["url"]] if post.get("url") and video_urls else []
                sources += [u for u in video_urls if u != post.get("url")]
                return post, [], sources
            downloaded = downloader.download_media_items(media_items, post["id"]) if media_items else []
            return post, downloaded, []

        progress(f"Processing {len(all_posts)} post(s) with parallel downloads…")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(download_task, p): p for p in all_posts}
            for idx, future in enumerate(as_completed(futures), 1):
                post, downloaded, audio_sources = future.result()
                post_id = post["id"]
                post_url = post["url"]
                post_type = post.get("type", "Post")
                description = post.get("description", "")

                progress(f"  [{idx}/{len(all_posts)}] {post_type}: {post_url}")

                if downloaded:
                    progress(f"    Downloaded {len(downloaded)} file(s).")
                elif is_whisper and audio_sources:
                    progress(f"    Audio sources: {len(audio_sources)}")
                else:
                    progress("    No media — caption only.")

                try:
                    progress("    Analyzing…")
                    if is_whisper:
                        extracted = analyzer.extract_knowledge(
                            downloaded, description, video_urls=audio_sources
                        )
                    else:
                        extracted = analyzer.extract_knowledge(downloaded, description)

                    indexer.index_post(
                        post_id=post_id,
                        url=post_url,
                        creator_username=username,
                        post_type=post_type,
                        description=description,
                        extracted_text=extracted,
                    )
                    new_post_ids.append(post_id)
                    progress(f"    ✓ Indexed {post_id}")

                except Exception as e:
                    progress(f"    ✗ Error on {post_id}: {e}")
                    failed_ids.append(post_id)

                finally:
                    if downloaded and not keep_media:
                        downloader.cleanup_items(downloaded)

    except Exception as e:
        progress(f"Pipeline error: {e}")
        return {
            "processed": len(new_post_ids),
            "skipped_known": len(known_ids),
            "failed": len(failed_ids),
            "total_indexed": len(known_ids) + len(new_post_ids),
            "last_scraped_at": profile.last_scraped_at,
            "error": str(e),
        }

    # Update profile stats
    elapsed = time.time() - run_start
    profile.last_scraped_at = run_start
    db = get_session()
    try:
        profile.total_posts_scraped = repo.count_posts(db, creator_username=username)
    finally:
        db.close()
    save_ig_profile(profile)

    progress(f"Done in {elapsed:.1f}s — indexed {len(new_post_ids)}, failed {len(failed_ids)}.")

    return {
        "processed": len(new_post_ids),
        "skipped_known": len(known_ids),
        "failed": len(failed_ids),
        "total_indexed": len(known_ids) + len(new_post_ids),
        "last_scraped_at": run_start,
    }
