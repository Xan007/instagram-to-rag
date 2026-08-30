"""Profile pipeline: scrape -> filter -> download -> analyze -> index."""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from config.profiles import load_profile, save_profile
from src.pipeline._common import Progress, download_with_ytdlp, echo


def run_profile(
    username: str,
    *,
    newer_than: Optional[str] = None,
    keep_media: bool = False,
    progress: Progress = echo,
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

        mode = profile.analysis_mode
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
