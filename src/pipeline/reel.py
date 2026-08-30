"""Add individual reels/posts by URL through the pipeline."""
import os
import time
from typing import Any, Dict, List, Optional

from config.profiles import ProfileConfig, load_profile, save_profile
from config.settings import load_settings
from config.utils import shortcode_from_url
from src.pipeline._common import Progress, download_with_ytdlp, echo


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
    progress: Progress = echo,
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
    from src.scraper.apify_post_scraper import ApifyPostScraper

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

            mode = settings.engine
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
                    downloaded_files = download_with_ytdlp(meta["url"], reel_id, prefix="reel") or []
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
                if reel_id in profile.failed_ids:
                    profile.failed_ids.remove(reel_id)
                save_profile(profile)

            added.append({"id": reel_id, "url": url})
        except Exception as e:
            failed.append({"url": url, "error": str(e)})
            if profile and reel_id:
                if reel_id not in profile.failed_ids:
                    profile.failed_ids.append(reel_id)
                    save_profile(profile)
        finally:
            if downloaded_files and not keep_media:
                downloader.cleanup_items(downloaded_files)

    return {"added": added, "failed": failed}
