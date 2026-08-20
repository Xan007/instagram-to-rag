import typer
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from config.settings import load_settings, save_settings
from config.profiles import ProfileConfig, load_profile, save_profile, list_profiles, delete_profile

app = typer.Typer(
    name="ig-rag",
    help="ig-rag -- Extract knowledge from Instagram profiles and index into a vector database for RAG.",
    add_completion=False,
)
profile_app = typer.Typer(help="Manage Instagram profiles.")
app.add_typer(profile_app, name="profile")

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


@app.command()
def run(
    username: str = typer.Argument(..., help="Instagram username to process"),
    newer_than: Optional[str] = typer.Option(
        None,
        "--newer-than",
        help="Only scrape posts newer than this date. Accepts YYYY-MM-DD, ISO-8601, or Unix timestamp.",
    ),
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
                    if downloaded_files:
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
            console.print("\n[bold yellow]Referenced Sources:[/bold yellow]")
            for src in result["sources"]:
                console.print(f" - @{src['creator']}: {src['url']}")
    except Exception as e:
        console.print(f"[bold red]Query failed:[/bold red] {e}")


def main():
    app()


if __name__ == "__main__":
    main()
