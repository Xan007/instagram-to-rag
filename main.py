import typer
from pathlib import Path
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from config.settings import load_settings, save_settings
from config.profiles import ProfileConfig, load_profile, save_profile, list_profiles, delete_profile

app = typer.Typer(
    name="instarag",
    help="instarag -- Extract knowledge from Instagram profiles and saved posts into a vector database for RAG.",
    add_completion=False,
)
profile_app = typer.Typer(help="Manage Instagram profiles.")
app.add_typer(profile_app, name="profile")
saved_app = typer.Typer(help="Import and process Instagram saved posts from your data export.")
app.add_typer(saved_app, name="saved")

console = Console()


@app.command()
def config(
    audio_only: bool = typer.Option(None, "--audio-only", help="Process only audio globally"),
    engine: str = typer.Option(None, "--engine", help="'gemini' or 'local_whisper'"),
    embed_provider: str = typer.Option(None, "--embed-provider", help="'gemini' or 'local'"),
    ig_username: str = typer.Option(None, "--ig-username", help="Your Instagram username to load session and prevent 429 blocks"),
    scraper_engine: str = typer.Option(None, "--scraper-engine", help="'apify' or 'instaloader'"),
):
    """Configure the global pipeline settings."""
    settings = load_settings()

    updated = False
    if scraper_engine is not None:
        if scraper_engine not in ["apify", "instaloader"]:
            console.print("[bold red]Invalid scraper engine. Use 'apify' or 'instaloader'.[/bold red]")
            raise typer.Exit(1)
        settings.scraper_engine = scraper_engine
        updated = True
    if ig_username is not None:
        settings.ig_username = ig_username
        updated = True
    if audio_only is not None:
        settings.audio_only = audio_only
        updated = True
    if engine is not None:
        if engine not in ["gemini", "local_whisper"]:
            console.print("[bold red]Invalid engine. Use 'gemini' or 'local_whisper'.[/bold red]")
            raise typer.Exit(1)
        settings.engine = engine
        updated = True
    if embed_provider is not None:
        if embed_provider not in ["gemini", "local"]:
            console.print("[bold red]Invalid embed provider. Use 'gemini' or 'local'.[/bold red]")
            raise typer.Exit(1)
        settings.embed_provider = embed_provider
        updated = True

    if updated:
        save_settings(settings)
        console.print("[bold green]Global settings updated successfully![/bold green]")

    console.print("\n[bold]Current Global Settings:[/bold]")
    for key, value in settings.model_dump().items():
        console.print(f"  {key}: {value}")


@profile_app.command("add")
def add_profile(
    username: str = typer.Argument(..., help="Instagram username"),
    interests: Optional[str] = typer.Option(None, "--interests", help="Comma-separated interests (e.g. 'food, diet')"),
    max_posts: Optional[int] = typer.Option(None, "--max-posts", help="Limit of posts to process per run"),
    analysis_mode: Optional[str] = typer.Option(
        None,
        "--analysis-mode",
        help="'gemini' | 'local_whisper' | 'openai_whisper'. Whisper modes transcribe audio instead of multimodal analysis.",
    ),
    audio_only: Optional[bool] = typer.Option(None, "--audio-only", help="If true, only audio (transcription) is processed"),
):
    """Add a new profile, or update only the fields you pass for an existing one."""
    if analysis_mode is not None and analysis_mode not in ["gemini", "local_whisper", "openai_whisper"]:
        console.print("[bold red]Invalid analysis mode. Use 'gemini', 'local_whisper' or 'openai_whisper'.[/bold red]")
        raise typer.Exit(1)

    profile = load_profile(username)
    if profile:
        if interests is not None:
            profile.interests = interests
        if max_posts is not None:
            profile.max_posts = max_posts
        if analysis_mode is not None:
            profile.analysis_mode = analysis_mode
        if audio_only is not None:
            profile.audio_only = audio_only
        console.print(f"[bold yellow]Updated existing profile @{username}[/bold yellow]")
    else:
        profile = ProfileConfig(
            username=username,
            interests=interests or "",
            max_posts=max_posts or 50,
            analysis_mode=analysis_mode or "gemini",
            audio_only=bool(audio_only),
        )
        console.print(f"[bold green]Added new profile @{username}[/bold green]")

    save_profile(profile)
    console.print(f"Interests: {profile.interests} | Max posts: {profile.max_posts} | Analysis mode: {profile.analysis_mode} | Audio only: {profile.audio_only}")


@profile_app.command("show")
def show_profile(
    username: str = typer.Argument(..., help="Instagram username"),
):
    """Show the full configuration and state of a profile."""
    profile = load_profile(username)
    if not profile:
        console.print(f"[bold red]Profile @{username} not found.[/bold red]")
        raise typer.Exit(1)

    console.print(f"[bold]Profile @{profile.username}[/bold]")
    console.print(f"  Interests:      {profile.interests}")
    console.print(f"  Max posts:      {profile.max_posts}")
    console.print(f"  Analysis mode:  {profile.analysis_mode}")
    console.print(f"  Audio only:     {profile.audio_only}")
    console.print(f"  Processed:      {len(profile.processed_ids)} posts")
    console.print(f"  Failed:         {len(getattr(profile, 'failed_ids', []))} posts")
    if profile.failed_ids:
        console.print(f"  Failed IDs:     {', '.join(profile.failed_ids)}")


@profile_app.command("list")
def list_all_profiles():
    """List all configured profiles."""
    profiles = list_profiles()
    if not profiles:
        console.print("[yellow]No profiles configured yet.[/yellow]")
        return

    console.print("[bold blue]Configured Profiles:[/bold blue]")
    for username in profiles:
        p = load_profile(username)
        if p:
            console.print(
                f"  - @[bold]{p.username}[/bold] | mode: {p.analysis_mode} | audio_only: {p.audio_only} | "
                f"processed: {len(p.processed_ids)} | failed: {len(getattr(p, 'failed_ids', []))}"
            )


@profile_app.command("remove")
def remove_profile(
    username: str = typer.Argument(..., help="Instagram username"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Remove a profile and its tracking state."""
    if not yes:
        if not typer.confirm(f"Delete profile @{username} and its processed history?"):
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)
    if delete_profile(username):
        console.print(f"[bold green]Removed profile @{username}[/bold green]")
    else:
        console.print(f"[bold red]Profile @{username} not found.[/bold red]")
        raise typer.Exit(1)


@profile_app.command("reset")
def reset_profile(
    username: str = typer.Argument(..., help="Instagram username"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Clear the processed/failed history so every post is re-processed."""
    profile = load_profile(username)
    if not profile:
        console.print(f"[bold red]Profile @{username} not found.[/bold red]")
        raise typer.Exit(1)

    total = len(profile.processed_ids) + len(getattr(profile, "failed_ids", []))
    if not yes:
        if not typer.confirm(f"Clear {total} tracked post(s) for @{username}?"):
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)
    profile.processed_ids = []
    profile.failed_ids = []
    save_profile(profile)
    console.print(f"[bold green]Reset @{username}: processed and failed history cleared.[/bold green]")


@saved_app.command("import")
def saved_import(
    path: Path = typer.Argument(..., help="Path to the Instagram export .zip or saved_posts.json"),
):
    """Import saved posts from an Instagram data export.

    For .zip files, ONLY your_instagram_activity/saved/saved_posts.json is
    extracted; every other file (personal data, media, logs) is discarded.
    """
    try:
        from config.saved import import_saved_posts, SAVED_POSTS_FILE
        state = import_saved_posts(path)
    except Exception as e:
        console.print(f"[bold red]Import failed:[/bold red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold green]Imported {state.total} saved posts[/bold green] from {state.source}")
    console.print(f"Stored at {SAVED_POSTS_FILE} (all other export data was discarded for privacy).")


@saved_app.command("status")
def saved_status():
    """Show the import and processing status of saved posts."""
    from config.saved import SAVED_POSTS_FILE, STATE_FILE, load_state

    if not SAVED_POSTS_FILE.exists():
        console.print("[yellow]No saved posts imported yet. Use 'saved import'.[/yellow]")
        return

    state = load_state()
    if not STATE_FILE.exists():
        state.total = 0
    console.print(f"[bold]Saved posts:[/bold] {state.total} | imported: {state.imported_at}")
    console.print(f"Source: {state.source}")
    console.print(f"Processed: {len(state.processed_ids)} | Failed: {len(state.failed_ids)} | Pending: {state.total - len(state.processed_ids)}")
    if state.failed_ids:
        console.print(f"Failed IDs: {', '.join(state.failed_ids)}")


@saved_app.command("process")
def saved_process(
    limit: Optional[int] = typer.Option(None, "--limit", help="Only process the first N pending posts (useful for testing)"),
    caption_only: bool = typer.Option(False, "--caption-only", help="Skip media download and analyze captions only"),
    workers: int = typer.Option(4, "--workers", help="Number of parallel workers for download + analysis"),
):
    """Process ALL imported saved posts (no interest filter) and index their knowledge.

    Posts already processed by any profile (or by a previous saved run) are
    skipped. Each post's media is downloaded with yt-dlp and analyzed in
    parallel workers; if media can't be fetched, the caption is used.
    """
    import json as json_mod
    import glob
    import os
    from yt_dlp import YoutubeDL
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from typing import Tuple

    from config.saved import SAVED_POSTS_FILE, load_state, parse_saved_posts, save_state
    from config.profiles import list_profiles, load_profile

    if not SAVED_POSTS_FILE.exists():
        console.print("[bold red]No saved posts imported. Run 'saved import' first.[/bold red]")
        raise typer.Exit(1)

    data = json_mod.loads(SAVED_POSTS_FILE.read_text(encoding="utf-8"))
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

    console.print(f"Total saved posts: {len(items)} | Already known (profiles/saved): {len(already)} | To process: {len(pending)}")
    if newly_known:
        console.print(f"[dim]Marked {len(newly_known)} posts as processed because they were already indexed via a profile.[/dim]")

    if not pending:
        save_state(state)
        console.print("[green]Nothing to process.[/green]")
        return

    try:
        from src.analyzer.gemini_analyzer import GeminiAnalyzer
        from src.indexer.pinecone_indexer import PineconeIndexer
        analyzer = GeminiAnalyzer()
        indexer = PineconeIndexer()
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        console.print("Please check your .env file for GEMINI_API_KEY, PINECONE_API_KEY, etc.")
        raise typer.Exit(1)

    def _download_with_ytdlp(url: str, pid: str) -> Optional[str]:
        """Download a reel/post with yt-dlp (video+audio merged via ffmpeg). Raises on failure."""
        os.makedirs("data/raw", exist_ok=True)
        outtmpl = os.path.join("data/raw", f"saved_{pid}.%(ext)s")
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "retries": 3,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        if os.path.exists(filename):
            return [{"type": "video", "path": filename}]
        candidates = glob.glob(outtmpl.replace("%(ext)s", ".*"))
        return [{"type": "video", "path": candidates[0]}] if candidates else None

    def _download_with_instaloader(pid: str) -> Optional[List[Dict[str, str]]]:
        """Download a reel/post/sidecar with an authenticated instaloader session."""
        import instaloader
        import requests

        settings = load_settings()
        if not settings.ig_username:
            return None
        L = instaloader.Instaloader()
        try:
            L.load_session_from_file(settings.ig_username)
        except Exception:
            return None
        post = instaloader.Post.from_shortcode(L.context, pid)

        media_srcs = []
        if post.typename == "Sidecar":
            for node in post.get_sidecar_nodes():
                if node.get("video_url"):
                    media_srcs.append(("video", node["video_url"]))
                else:
                    media_srcs.append(("image", node["display_url"]))
        elif post.is_video:
            media_srcs.append(("video", post.video_url))
        else:
            media_srcs.append(("image", post.url))
        if not media_srcs:
            return None

        os.makedirs("data/raw", exist_ok=True)
        files = []
        for idx, (m_type, url) in enumerate(media_srcs):
            ext = ".mp4" if m_type == "video" else ".jpg"
            file_path = os.path.join("data/raw", f"saved_{pid}_{idx}{ext}")
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            files.append({"type": m_type, "path": file_path})
        return files

    def process_item(item: Dict[str, Any]) -> Tuple[str, str, Optional[Exception]]:
        """Download media (if any) and analyze + index one saved post. Returns (status, id, error)."""
        pid = item["id"]
        description = (item["title"] + "\n" + item["caption"]).strip()
        post = {
            "id": pid,
            "url": item["url"],
            "type": "Reel" if "/reel/" in item["url"] else "Post",
            "description": description,
            "media_items": [],
        }
        media_files = []
        try:
            if not caption_only:
                try:
                    media_files = _download_with_ytdlp(item["url"], pid) or []
                except Exception as e:
                    console.print(f"[dim]yt-dlp failed for {pid}: {e}[/dim]")
                if not media_files:
                    media_files = _download_with_instaloader(pid) or []
                    if media_files:
                        console.print(f"[dim]{pid}: fetched via instaloader session.[/dim]")
                if not media_files:
                    console.print(f"[dim]{pid}: no media available; will use caption if present.[/dim]")

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
    console.print(f"[bold]Processing {len(pending)} posts with {workers} parallel workers (download + analysis)...[/bold]")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_item = {executor.submit(process_item, item): item for item in pending}
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            pid = item["id"]
            status, result_pid, error = future.result()
            if status == "ok":
                state.processed_ids.append(result_pid)
                if result_pid in state.failed_ids:
                    state.failed_ids.remove(result_pid)
                processed += 1
                console.print(f"[green]Extracted knowledge for {result_pid}[/green] | {item['url']}")
            elif status == "skipped":
                state.processed_ids.append(result_pid)
                if result_pid in state.failed_ids:
                    state.failed_ids.remove(result_pid)
                skipped += 1
                console.print(f"[yellow]Skipped {result_pid} (no caption/title and no media)[/yellow]")
            else:
                if result_pid not in state.failed_ids:
                    state.failed_ids.append(result_pid)
                failed += 1
                console.print(f"[red]Error analyzing saved post {result_pid}:[/red] {error}")
            save_state(state)

    console.print(f"\n[bold green]Saved processing finished![/bold green] Processed {processed}, skipped {skipped}, failed {failed}.")
    console.print(f"Total processed: {len(state.processed_ids)} | Failed: {len(state.failed_ids)}")


@saved_app.command("reset")
def saved_reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Clear the processed/failed history so every saved post is re-processed."""
    from config.saved import load_state, save_state

    state = load_state()
    total = len(state.processed_ids) + len(state.failed_ids)
    if not yes:
        if not typer.confirm(f"Clear {total} tracked saved post(s)?"):
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)
    state.processed_ids = []
    state.failed_ids = []
    save_state(state)
    console.print("[bold green]Saved history cleared. Next 'saved process' will re-process everything.[/bold green]")


@app.command()
def auth_session(
    username: str = typer.Argument(..., help="Instagram username for the session file"),
    browser: str = typer.Option("edge", "--browser", help="'edge', 'chrome', or 'firefox'"),
):
    """Create an instaloader session from your logged-in browser cookies (no password needed).

    Instagram blocks automated logins ('fail' status even with the correct
    password), so log into instagram.com in your browser first, then run this.
    """
    import browser_cookie3
    import instaloader

    try:
        if browser == "edge":
            cj = browser_cookie3.edge(domain_name=".instagram.com")
        elif browser == "chrome":
            cj = browser_cookie3.chrome(domain_name=".instagram.com")
        elif browser == "firefox":
            cj = browser_cookie3.firefox(domain_name=".instagram.com")
        else:
            console.print("[bold red]Unsupported browser. Use 'edge', 'chrome', or 'firefox'.[/bold red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Could not read {browser} cookies:[/bold red] {type(e).__name__}: {e}")
        console.print("Modern Chrome/Edge encrypt cookies with Windows app-bound encryption that cannot be decrypted externally.")
        console.print("Use Firefox instead: log into instagram.com in Firefox, CLOSE Firefox, then run:")
        console.print(f"  uv run python main.py auth-session {username} --browser firefox")
        raise typer.Exit(1)

    if not any(c.name == "sessionid" for c in cj):
        console.print("[bold red]No active Instagram session found in the selected browser.[/bold red]")
        console.print("1) Log into instagram.com in that browser (desktop website, not the app).")
        console.print("2) Complete any security check Instagram shows.")
        console.print("3) Run this command again.")
        raise typer.Exit(1)

    L = instaloader.Instaloader()
    L.context._session.cookies.update(cj)
    L.context.username = username
    L.save_session_to_file()

    settings = load_settings()
    if settings.ig_username != username:
        settings.ig_username = username
        save_settings(settings)
    console.print(f"[bold green]Session saved as session-{username} and ig_username configured — instaloader fallback enabled.[/bold green]")


@app.command()
def run(
    username: str = typer.Argument(..., help="Instagram username to process"),
    newer_than: Optional[str] = typer.Option(
        None,
        "--newer-than",
        help="Only scrape posts newer than this date. Accepts YYYY-MM-DD, ISO-8601, or Unix timestamp.",
    ),
    keep_media: bool = typer.Option(False, "--keep-media", help="Keep downloaded media files in data/raw after processing"),
):
    """Run the pipeline to extract and index knowledge from a profile."""
    profile = load_profile(username)
    if not profile:
        console.print(f"[bold red]Profile @{username} not found. Add it first using 'profile add'[/bold red]")
        raise typer.Exit(1)

    settings = load_settings()
    console.print(f"[bold blue]Starting pipeline for @{username}...[/bold blue]")
    console.print(f"Interests: {profile.interests}")
    console.print(f"Max posts: {profile.max_posts}")
    console.print(f"Scraper Engine: {settings.scraper_engine}")
    console.print(f"Already processed: {len(profile.processed_ids)} posts | Failed: {len(getattr(profile, 'failed_ids', []))} posts")
    if newer_than:
        console.print(f"Date filter: only posts newer than {newer_than}")

    from src.scraper.local_instaloader import LocalInstaloaderScraper
    from src.scraper.apify_scraper import ApifyScraper
    from src.filter.interest_filter import InterestFilter
    from src.downloader.media_downloader import MediaDownloader
    from src.analyzer.gemini_analyzer import GeminiAnalyzer
    from src.indexer.pinecone_indexer import PineconeIndexer

    if settings.scraper_engine == "apify":
        scraper = ApifyScraper(only_posts_newer_than=newer_than)
    else:
        scraper = LocalInstaloaderScraper(settings.ig_username)

    downloader = MediaDownloader()

    try:
        interest_filter = InterestFilter()

        mode = getattr(profile, "analysis_mode", "gemini")
        is_whisper = mode in ("local_whisper", "openai_whisper")
        if mode == "local_whisper":
            from src.analyzer.whisper_analyzer import WhisperAnalyzer
            analyzer = WhisperAnalyzer(mode="local_whisper")
        elif mode == "openai_whisper":
            from src.analyzer.whisper_analyzer import WhisperAnalyzer
            analyzer = WhisperAnalyzer(mode="openai_whisper")
        else:
            analyzer = GeminiAnalyzer()

        indexer = PineconeIndexer()
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        console.print("Please check your .env file for GEMINI_API_KEY, PINECONE_API_KEY, etc.")
        raise typer.Exit(1)

    new_processed_ids = []

    try:
        console.print("\n[bold]Fetching post metadata...[/bold]")
        console.print(f"Posts already in processed_ids ({len(profile.processed_ids)}) will be skipped by the scraper.")
        all_posts: List[Dict[str, Any]] = list(
            scraper.get_posts_metadata(username, profile.max_posts, profile.processed_ids)
        )
        console.print(f"Retrieved {len(all_posts)} new candidates to evaluate.")

        if not all_posts:
            console.print("[green]No new posts to process.[/green]")
            return

        console.print(f"\n[bold]Running batch interest filtering on {len(all_posts)} posts...[/bold]")
        matching_ids = interest_filter.filter_batch(all_posts, profile.interests)
        matching_posts = [p for p in all_posts if p["id"] in matching_ids]
        console.print(f"[bold green]Filter matched {len(matching_posts)}/{len(all_posts)} relevant posts![/bold green]")
        for post in matching_posts:
            n_media = len(post.get("media_items", []))
            console.print(f"  - {post['id']} ({post.get('type', 'Post')}, {n_media} media): {post.get('url', '')}")

        if not matching_posts:
            console.print("[yellow]No posts matched the target interests.[/yellow]")
            return

        if is_whisper:
            console.print(f"\n[bold]Fetching audio for videos (yt-dlp audio-only) and transcribing...[/bold]")
        else:
            console.print(f"\n[bold]Downloading media in parallel (4 workers) and analyzing...[/bold]")

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

                console.print(f"\n[cyan]Processing Post ({post.get('type', 'Post')}): {post_url}[/cyan]")

                if is_whisper:
                    if audio_sources:
                        console.print(f"Audio sources: {len(audio_sources)} (yt-dlp audio-only)")
                    else:
                        console.print("[yellow]No video sources; will use the caption only.[/yellow]")
                elif downloaded_files:
                    breakdown: Dict[str, int] = {}
                    for f in downloaded_files:
                        f_type = f.get("type", "unknown")
                        breakdown[f_type] = breakdown.get(f_type, 0) + 1
                    console.print(f"Downloaded {len(downloaded_files)} media file(s): {breakdown}")
                else:
                    console.print("[yellow]No media downloaded (text-only post or all downloads failed).[/yellow]")

                try:
                    console.print("Analyzing content...")
                    if is_whisper:
                        extracted_text = analyzer.extract_knowledge(
                            downloaded_files, post.get("description", ""), video_urls=audio_sources
                        )
                    else:
                        extracted_text = analyzer.extract_knowledge(downloaded_files, post.get("description", ""))
                    console.print(f"[green]Successfully extracted knowledge for {post_id}![/green]")

                    indexer.index_post(username, post, extracted_text)

                    profile.processed_ids.append(post_id)
                    new_processed_ids.append(post_id)

                    save_profile(profile)

                except Exception as e:
                    console.print(f"[red]Error analyzing post {post_id}:[/red] {e}")
                    if hasattr(profile, "failed_ids"):
                        if post_id not in profile.failed_ids:
                            profile.failed_ids.append(post_id)
                            save_profile(profile)
                finally:
                    if downloaded_files and not keep_media:
                        downloader.cleanup_items(downloaded_files)

    except Exception as e:
        console.print(f"[bold red]An error occurred during pipeline execution:[/bold red] {e}")

    console.print(f"\n[bold green]Pipeline finished![/bold green] Processed {len(new_processed_ids)} new posts.")
    console.print(f"Profile @{username} now has {len(profile.processed_ids)} processed and {len(getattr(profile, 'failed_ids', []))} failed.")


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to ask the knowledge base"),
    creator: Optional[str] = typer.Option(None, "--creator", "-c", help="Filter by specific Instagram creator"),
):
    """Ask a question based on the indexed knowledge base."""
    console.print(f"[bold blue]Querying RAG Engine for:[/bold blue] [italic]'{question}'[/italic]")
    if creator:
        console.print(f"Filtered by creator: @{creator}")

    from src.rag.query_engine import QueryEngine
    try:
        engine = QueryEngine()
        result = engine.query(question=question, username=creator)

        console.print("\n[bold green]=== Answer ===[/bold green]\n")
        console.print(result["answer"])

        if result["sources"]:
            import re
            cited = set(re.findall(r"\[Source (\d+)\]", result["answer"]))
            cited_sources = [(i, s) for i, s in enumerate(result["sources"], start=1)
                             if not cited or str(i) in cited]
            console.print("\n[bold yellow]Referenced Sources:[/bold yellow]")
            for i, src in cited_sources:
                score = f" (score: {src['score']:.4f})" if src.get("score") is not None else ""
                console.print(f" - [Source {i}] @{src['creator']}: {src['url']}{score}")
    except Exception as e:
        console.print(f"[bold red]Query failed:[/bold red] {e}")


def main():
    app()


if __name__ == "__main__":
    main()
