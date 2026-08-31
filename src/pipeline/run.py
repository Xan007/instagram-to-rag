"""Profile pipeline: scrape -> filter -> download -> analyze -> index."""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.profiles import load_profile, save_profile
from src.pipeline._common import Progress, download_with_ytdlp, echo


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_profile(
    username: str,
    *,
    newer_than: Optional[str] = None,
    keep_media: bool = False,
    progress: Progress = echo,
) -> Dict[str, Any]:
    """Run the full scrape -> filter -> download -> analyze -> index pipeline for a profile.

    Returns a dict with keys:
      processed, failed, skipped, processed_ids, total_processed, total_failed,
      last_scraped_at (Unix ts), error (str, only if a top-level exception occurred).
    """
    from src.scraper.apify_scraper import ApifyScraper
    from src.filter.interest_filter import InterestFilter
    from src.downloader.media_downloader import MediaDownloader
    from src.analyzer.gemini_analyzer import GeminiAnalyzer
    from src.indexer.pinecone_indexer import PineconeIndexer

    profile = load_profile(username)
    if not profile:
        raise ValueError(f"Profile @{username} not found. Add it first using 'profile add'")

    run_start_ts = time.time()
    run_start_iso = _now_iso()

    # ── Summary header ────────────────────────────────────────────────────
    progress(f"[bold]Pipeline started for @{username}[/bold] at {run_start_iso[:19]}Z")
    progress(
        f"  Interests: {profile.interests or '(none)'} | "
        f"Max posts: {profile.max_posts} | "
        f"Mode: {profile.analysis_mode}"
    )
    progress(
        f"  Already processed: {len(profile.processed_ids)} | "
        f"Failed (retryable): {len(profile.failed_ids)}"
    )
    if newer_than:
        progress(f"  Date filter: only posts newer than {newer_than}")
    elif profile.last_scraped_at:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(profile.last_scraped_at, tz=timezone.utc)
        progress(f"  Last scraped: {dt.isoformat()[:19]}Z (auto date-filter not applied — use 'profile update' for that)")

    # ── Component initialisation ──────────────────────────────────────────
    scraper = ApifyScraper(only_posts_newer_than=newer_than)
    downloader = MediaDownloader()

    try:
        interest_filter = InterestFilter()
        mode = profile.analysis_mode
        is_whisper = mode in ("local_whisper", "openai_whisper")
        if is_whisper:
            from src.analyzer.whisper_analyzer import WhisperAnalyzer
            analyzer = WhisperAnalyzer(mode=mode)
        else:
            analyzer = GeminiAnalyzer()
        indexer = PineconeIndexer()
    except ValueError as e:
        raise ValueError(f"Configuration error: {e}. Check your .env for GEMINI_API_KEY, PINECONE_API_KEY, etc.")

    new_processed_ids: List[str] = []
    new_failed_count = 0

    # ── Mark run start so even an empty run updates last_run_at ──────────
    profile.last_run_at = run_start_iso
    save_profile(profile)

    try:
        # ── Scrape ───────────────────────────────────────────────────────
        progress("Fetching post metadata from Apify…")
        all_posts: List[Dict[str, Any]] = list(
            scraper.get_posts_metadata(username, profile.max_posts, profile.processed_ids)
        )
        progress(f"  Retrieved {len(all_posts)} new candidate(s).")

        if not all_posts:
            progress("  No new posts found — profile is up to date.")
            profile.last_scraped_at = run_start_ts
            save_profile(profile)
            return {
                "processed": 0,
                "failed": 0,
                "skipped": 0,
                "processed_ids": [],
                "total_processed": len(profile.processed_ids),
                "total_failed": len(profile.failed_ids),
                "last_scraped_at": run_start_ts,
                "message": "No new posts to process.",
            }

        # ── Interest filter ───────────────────────────────────────────────
        progress(f"Running interest filter on {len(all_posts)} post(s)…")
        matching_ids = interest_filter.filter_batch(all_posts, profile.interests)
        matching_posts = [p for p in all_posts if p["id"] in matching_ids]
        skipped_by_filter = len(all_posts) - len(matching_posts)
        progress(
            f"  Matched {len(matching_posts)}/{len(all_posts)} post(s) "
            f"({skipped_by_filter} filtered out by interest)."
        )

        if not matching_posts:
            profile.last_scraped_at = run_start_ts
            save_profile(profile)
            return {
                "processed": 0,
                "failed": 0,
                "skipped": skipped_by_filter,
                "processed_ids": [],
                "total_processed": len(profile.processed_ids),
                "total_failed": len(profile.failed_ids),
                "last_scraped_at": run_start_ts,
                "message": "No posts matched the target interests.",
            }

        # ── Download task (per-post) ───────────────────────────────────────
        def download_task(post: Dict[str, Any]):
            media_items = post.get("media_items", [])
            if is_whisper:
                video_urls = [m["url"] for m in media_items if m.get("type") == "video"]
                sources = []
                if post.get("url") and video_urls:
                    sources.append(post["url"])
                sources += [u for u in video_urls if u != post.get("url")]
                return post, [], sources
            downloaded = []
            if media_items:
                downloaded = downloader.download_media_items(media_items, post["id"])
            return post, downloaded, []

        # ── Parallel download + serial analyze/index ──────────────────────
        progress(f"Processing {len(matching_posts)} post(s) with parallel downloads…")
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_post = {executor.submit(download_task, post): post for post in matching_posts}

            for idx, future in enumerate(as_completed(future_to_post), start=1):
                post, downloaded_files, audio_sources = future.result()
                post_id = post["id"]
                post_url = post["url"]
                post_type = post.get("type", "Post")

                progress(
                    f"  [{idx}/{len(matching_posts)}] {post_type}: {post_url}"
                )

                if is_whisper:
                    progress(
                        f"    Audio sources: {len(audio_sources)}"
                        if audio_sources
                        else "    No video sources — will use caption."
                    )
                elif downloaded_files:
                    progress(f"    Downloaded {len(downloaded_files)} media file(s).")
                else:
                    progress("    No media downloaded (text-only or all downloads failed).")

                try:
                    progress("    Analyzing…")
                    if is_whisper:
                        extracted_text = analyzer.extract_knowledge(
                            downloaded_files, post.get("description", ""), video_urls=audio_sources
                        )
                    else:
                        extracted_text = analyzer.extract_knowledge(
                            downloaded_files, post.get("description", "")
                        )

                    indexer.index_post(username, post, extracted_text)

                    profile.processed_ids.append(post_id)
                    # Remove from failed list if it was there before
                    if post_id in profile.failed_ids:
                        profile.failed_ids.remove(post_id)
                    new_processed_ids.append(post_id)
                    save_profile(profile)
                    progress(f"    ✓ Indexed post {post_id}")

                except Exception as e:
                    progress(f"    ✗ Error on {post_id}: {e}")
                    if post_id not in profile.failed_ids:
                        profile.failed_ids.append(post_id)
                        new_failed_count += 1
                        save_profile(profile)

                finally:
                    if downloaded_files and not keep_media:
                        downloader.cleanup_items(downloaded_files)

    except Exception as e:
        progress(f"Pipeline error: {e}")
        return {
            "processed": len(new_processed_ids),
            "failed": new_failed_count,
            "skipped": 0,
            "processed_ids": new_processed_ids,
            "total_processed": len(profile.processed_ids),
            "total_failed": len(profile.failed_ids),
            "last_scraped_at": profile.last_scraped_at,
            "error": str(e),
        }

    # ── Persist last_scraped_at on success ────────────────────────────────
    profile.last_scraped_at = run_start_ts
    save_profile(profile)

    elapsed = time.time() - run_start_ts
    progress(
        f"Pipeline finished in {elapsed:.1f}s — "
        f"processed {len(new_processed_ids)}, failed {new_failed_count}."
    )

    return {
        "processed": len(new_processed_ids),
        "failed": new_failed_count,
        "skipped": skipped_by_filter if matching_posts is not None else 0,
        "processed_ids": new_processed_ids,
        "total_processed": len(profile.processed_ids),
        "total_failed": len(profile.failed_ids),
        "last_scraped_at": run_start_ts,
    }
