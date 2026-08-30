"""Reusable pipeline operations shared by the CLI and the HTTP API.

Every public function accepts an optional ``progress`` callback used to
report step-by-step messages; callers decide how to render them (rich
console in the CLI, job logs in the API).
"""
import glob
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.paths import RAW_DIR
from config.profiles import ProfileConfig, list_profiles, load_profile, save_profile
from config.saved import SAVED_POSTS_FILE, load_state, parse_saved_posts, save_state
from config.settings import load_settings

Progress = Callable[[str], None]


def _echo(message: str) -> None:
    print(message)


def _download_with_ytdlp(url: str, pid: str, prefix: str = "saved") -> Optional[List[Dict[str, str]]]:
    """Download a reel/post with yt-dlp (video+audio merged via ffmpeg). Raises on failure."""
    from yt_dlp import YoutubeDL

    os.makedirs(RAW_DIR, exist_ok=True)
    outtmpl = os.path.join(RAW_DIR, f"{prefix}_{pid}.%(ext)s")
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 3,
        "concurrent_fragment_downloads": 4,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    if os.path.exists(filename):
        return [{"type": "video", "path": filename}]
    candidates = glob.glob(outtmpl.replace("%(ext)s", ".*"))
    return [{"type": "video", "path": candidates[0]}] if candidates else None


def run_profile(
    username: str,
    *,
    newer_than: Optional[str] = None,
    keep_media: bool = False,
    progress: Progress = _echo,
) -> Dict[str, Any]:
    """Run the full scrape -> filter -> download -> analyze -> index pipeline for a profile."""
    from src.scraper.apify_scraper import ApifyScraper
    from src.filter.interest_filter import InterestFilter
    from src.downloader.media_downloader import MediaDownloader
    from src.analyzer.gemini_analyzer import GeminiAnalyzer
    from src.indexer.pinecone_indexer import PineconeIndexer

    profile = load_profile(username)
    if not profile:
        raise ValueError(f"Profile @{username} not found. Add it first using 'profile add'")

    progress(f"Starting pipeline for @{username}")
    progress(f"Interests: {profile.interests}")
    progress(f"Max posts: {profile.max_posts}")
    progress(
        f"Already processed: {len(profile.processed_ids)} posts | "
        f"Failed: {len(profile.failed_ids)} posts"
    )
    if newer_than:
        progress(f"Date filter: only posts newer than {newer_than}")

    scraper = ApifyScraper(only_posts_newer_than=newer_than)

    downloader = MediaDownloader()

    try:
        interest_filter = InterestFilter()

        mode = getattr(profile, "analysis_mode", "gemini")
        is_whisper = mode in ("local_whisper", "openai_whisper")
        if is_whisper:
            from src.analyzer.whisper_analyzer import WhisperAnalyzer

            analyzer = WhisperAnalyzer(mode=mode)
        else:
            analyzer = GeminiAnalyzer()

        indexer = PineconeIndexer()
    except ValueError as e:
        raise ValueError(f"Configuration Error: {e}. Check your .env for GEMINI_API_KEY, PINECONE_API_KEY, etc.")

    new_processed_ids: List[str] = []

    try:
        progress("Fetching post metadata...")
        all_posts: List[Dict[str, Any]] = list(
            scraper.get_posts_metadata(username, profile.max_posts, profile.processed_ids)
        )
        progress(f"Retrieved {len(all_posts)} new candidates to evaluate.")

        if not all_posts:
            return {"processed": 0, "failed": 0, "processed_ids": [], "message": "No new posts to process."}

        progress(f"Running batch interest filtering on {len(all_posts)} posts...")
        matching_ids = interest_filter.filter_batch(all_posts, profile.interests)
        matching_posts = [p for p in all_posts if p["id"] in matching_ids]
        progress(f"Filter matched {len(matching_posts)}/{len(all_posts)} relevant posts!")

        if not matching_posts:
            return {"processed": 0, "failed": 0, "processed_ids": [], "message": "No posts matched the target interests."}

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

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_post = {executor.submit(download_task, post): post for post in matching_posts}

            for future in as_completed(future_to_post):
                post, downloaded_files, audio_sources = future.result()
                post_id = post["id"]
                post_url = post["url"]

                progress(f"Processing Post ({post.get('type', 'Post')}): {post_url}")

                if is_whisper:
                    if audio_sources:
                        progress(f"Audio sources: {len(audio_sources)} (yt-dlp audio-only)")
                    else:
                        progress("No video sources; will use the caption only.")
                elif downloaded_files:
                    progress(f"Downloaded {len(downloaded_files)} media file(s).")
                else:
                    progress("No media downloaded (text-only post or all downloads failed).")

                try:
                    progress("Analyzing content...")
                    if is_whisper:
                        extracted_text = analyzer.extract_knowledge(
                            downloaded_files, post.get("description", ""), video_urls=audio_sources
                        )
                    else:
                        extracted_text = analyzer.extract_knowledge(downloaded_files, post.get("description", ""))
                    progress(f"Successfully extracted knowledge for {post_id}!")

                    indexer.index_post(username, post, extracted_text)

                    profile.processed_ids.append(post_id)
                    new_processed_ids.append(post_id)
                    save_profile(profile)

                except Exception as e:
                    progress(f"Error analyzing post {post_id}: {e}")
                    if hasattr(profile, "failed_ids"):
                        if post_id not in profile.failed_ids:
                            profile.failed_ids.append(post_id)
                            save_profile(profile)
                finally:
                    if downloaded_files and not keep_media:
                        downloader.cleanup_items(downloaded_files)

    except Exception as e:
        progress(f"Pipeline error: {e}")
        return {
            "processed": len(new_processed_ids),
            "failed": len(profile.failed_ids),
            "processed_ids": new_processed_ids,
            "total_processed": len(profile.processed_ids),
            "error": str(e),
        }

    return {
        "processed": len(new_processed_ids),
        "failed": len(profile.failed_ids),
        "processed_ids": new_processed_ids,
        "total_processed": len(profile.processed_ids),
    }


def process_saved(
    *,
    limit: Optional[int] = None,
    caption_only: bool = False,
    workers: int = 4,
    progress: Progress = _echo,
) -> Dict[str, Any]:
    """Process ALL imported saved posts (no interest filter) and index their knowledge."""
    import json

    from src.analyzer.gemini_analyzer import GeminiAnalyzer
    from src.indexer.pinecone_indexer import PineconeIndexer

    if not SAVED_POSTS_FILE.exists():
        raise ValueError("No saved posts imported. Run 'saved import' first.")

    data = json.loads(SAVED_POSTS_FILE.read_text(encoding="utf-8"))
    items = parse_saved_posts(data)
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
                    media_files = _download_with_ytdlp(item["url"], pid) or []
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


def _reel_meta_via_ytdlp(url: str) -> Dict[str, Any]:
    """Fetch reel metadata with yt-dlp (no Instagram session needed)."""
    from yt_dlp import YoutubeDL

    ydl_opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise ValueError(
            f"Could not fetch reel metadata (Instagram session failed and yt-dlp fallback failed too: {e})."
        )
    shortcode = info.get("id")
    if not shortcode:
        raise ValueError(f"yt-dlp could not determine the reel id for {url}.")
    description = "\n".join(filter(None, [info.get("title"), info.get("description")]))
    return {"id": shortcode, "url": url, "type": "Reel", "description": description}


def add_reel(
    urls: List[str],
    *,
    creator: Optional[str] = None,
    caption_only: bool = False,
    keep_media: bool = False,
    progress: Progress = _echo,
) -> Dict[str, Any]:
    """Add one or more Instagram reel/post URLs through the full pipeline.

    Primary metadata/media source: apify/instagram-scraper (direct media URLs,
    downloaded straight over HTTP). Fallback per URL: yt-dlp for both
    metadata and download. No Instagram session is ever used.
    """
    from src.downloader.media_downloader import MediaDownloader
    from src.analyzer.gemini_analyzer import GeminiAnalyzer
    from src.analyzer.whisper_analyzer import WhisperAnalyzer
    from src.indexer.pinecone_indexer import PineconeIndexer
    from src.scraper.apify_post_scraper import shortcode_from_url

    urls = [u.strip() for u in urls if u and u.strip()]
    if not urls:
        raise ValueError("No URLs provided.")

    progress(f"Processing {len(urls)} reel/post URL(s)")
    if creator:
        progress(f"Associated with creator: @{creator}")

    settings = load_settings()
    profile = None
    if creator:
        profile = load_profile(creator)
        if profile is None:
            profile = ProfileConfig(username=creator, interests="")
            save_profile(profile)

    apify_meta: Dict[str, Dict[str, Any]] = {}
    try:
        from src.scraper.apify_post_scraper import ApifyPostScraper

        scraper_api = ApifyPostScraper()
        progress(f"Fetching metadata via {ApifyPostScraper.ACTOR_ID}...")
        for post in scraper_api.get_posts_by_urls(urls):
            apify_meta[post["id"]] = post
        progress(f"Apify returned metadata for {len(apify_meta)}/{len(urls)} URL(s).")
    except Exception as e:
        progress(f"Apify post scraper unavailable ({e}); using yt-dlp fallback.")

    added: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    analyzer = None
    indexer = None
    downloader = MediaDownloader()

    for url in urls:
        reel_id = None
        downloaded_files: List[Dict[str, str]] = []
        try:
            shortcode = shortcode_from_url(url)
            meta = apify_meta.get(shortcode)

            if meta is None:
                progress("No Apify metadata; falling back to yt-dlp.")
                meta = _reel_meta_via_ytdlp(url)
            else:
                meta = dict(meta)
                meta.setdefault("url", url)

            reel_id = meta["id"]
            description = meta.get("description", "")
            media_types = [m.get("type") for m in meta.get("media_items", [])]
            progress(f"Reel ID: {reel_id} | type: {meta.get('type')} | media: {media_types or 'none'}")
            progress(f"Description ({len(description)} chars): {description[:200] or '(no caption)'}")

            mode = getattr(settings, "analysis_mode", "gemini")
            is_whisper = mode in ("local_whisper", "openai_whisper")
            if analyzer is None:
                progress(f"Initializing analyzer (mode={mode}) and Pinecone indexer...")
                analyzer = WhisperAnalyzer(mode=mode) if is_whisper else GeminiAnalyzer()
                indexer = PineconeIndexer()

            try:
                if not caption_only and meta.get("media_items"):
                    progress(f"Downloading {len(meta['media_items'])} media item(s) over HTTP...")
                    downloaded_files = downloader.download_media_items(meta["media_items"], reel_id) or []
                if not downloaded_files and not caption_only:
                    progress("Direct media download empty; trying yt-dlp...")
                    downloaded_files = _download_with_ytdlp(meta["url"], reel_id, prefix="reel") or []
            except Exception as e:
                progress(f"Media download failed: {e} - using caption.")

            if downloaded_files:
                size_mb = sum(os.path.getsize(f["path"]) for f in downloaded_files if os.path.exists(f["path"])) / 1e6
                kinds = {}
                for f in downloaded_files:
                    kinds[f["type"]] = kinds.get(f["type"], 0) + 1
                progress(f"Downloaded {len(downloaded_files)} file(s) {kinds}, {size_mb:.1f} MB total")
            else:
                progress("No media downloaded; using caption.")

            progress("Analyzing content with Gemini...")
            t0 = time.perf_counter()
            if downloaded_files:
                extracted_text = analyzer.extract_knowledge(downloaded_files, description)
            else:
                extracted_text = analyzer.extract_knowledge([], description) if description else ""
            progress(f"Extracted {len(extracted_text)} chars of knowledge in {time.perf_counter() - t0:.1f}s")

            progress(f"Upserting vector for {reel_id} into Pinecone...")
            indexer.index_post(creator or "saved", meta, extracted_text)

            if profile:
                if reel_id not in profile.processed_ids:
                    profile.processed_ids.append(reel_id)
                if hasattr(profile, "failed_ids") and reel_id in profile.failed_ids:
                    profile.failed_ids.remove(reel_id)
                save_profile(profile)

            added.append({"id": reel_id, "url": url})
        except Exception as e:
            failed.append({"url": url, "error": str(e)})
            if profile and reel_id:
                if hasattr(profile, "failed_ids") and reel_id not in profile.failed_ids:
                    profile.failed_ids.append(reel_id)
                    save_profile(profile)
        finally:
            if downloaded_files and not keep_media:
                downloader.cleanup_items(downloaded_files)

    return {"added": added, "failed": failed}


def query_knowledge(
    question: str,
    creator: Optional[str] = None,
    *,
    top_k: int = 6,
    min_score: float = 0.35,
    mode: str = "grounded_plus",
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Query the knowledge base; history enables stateless multi-turn chat."""
    from src.rag.query_engine import QueryEngine

    engine = QueryEngine()
    return engine.query(
        question=question,
        username=creator,
        top_k=top_k,
        min_score=min_score,
        mode=mode,
        history=history,
    )
