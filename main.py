import typer
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich.console import Console

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
):
    """Configure the global pipeline settings."""
    from config.settings import load_settings, save_settings

    settings = load_settings()

    updated = False
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
    for key, value in vars(settings).items():
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
    from config.profiles import ProfileConfig, load_profile, save_profile

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
    from config.profiles import load_profile

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
    console.print(f"  Failed:         {len(profile.failed_ids)} posts")
    if profile.failed_ids:
        console.print(f"  Failed IDs:     {', '.join(profile.failed_ids)}")


@profile_app.command("list")
def list_all_profiles():
    """List all configured profiles."""
    from config.profiles import list_profiles, load_profile
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
                f"processed: {len(p.processed_ids)} | failed: {len(p.failed_ids)}"
            )


@profile_app.command("remove")
def remove_profile(
    username: str = typer.Argument(..., help="Instagram username"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Remove a profile and its tracking state."""
    from config.profiles import delete_profile

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
    from config.profiles import load_profile, save_profile

    profile = load_profile(username)
    if not profile:
        console.print(f"[bold red]Profile @{username} not found.[/bold red]")
        raise typer.Exit(1)

    total = len(profile.processed_ids) + len(profile.failed_ids)
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
    from src.pipeline import process_saved

    try:
        result = process_saved(
            limit=limit,
            caption_only=caption_only,
            workers=workers,
            progress=console.print,
        )
    except ValueError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1)

    console.print(
        f"\n[bold green]Saved processing finished![/bold green] "
        f"Processed {result['processed']}, skipped {result['skipped']}, failed {result['failed']}."
    )
    console.print(f"Total processed: {result['total_processed']} | Failed: {result.get('total_failed', 0)}")



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
def add_reel(
    urls: List[str] = typer.Argument(..., help="One or more Instagram reel/post URLs"),
    creator: Optional[str] = typer.Option(None, "--creator", "-c", help="Creator username for duplicate tracking"),
    caption_only: bool = typer.Option(False, "--caption-only", help="Skip media download, analyze caption only"),
    keep_media: bool = typer.Option(False, "--keep-media", help="Keep downloaded media files"),
):
    """Add one or more Instagram reels/posts by URL through the full pipeline."""
    from src.pipeline import add_reel as pipeline_add_reel

    try:
        result = pipeline_add_reel(
            list(urls),
            creator=creator,
            caption_only=caption_only,
            keep_media=keep_media,
            progress=console.print,
        )
    except ValueError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1)

    for item in result["added"]:
        console.print(f"[bold green]Reel added successfully! ID: {item['id']}[/bold green] | {item['url']}")
    for item in result["failed"]:
        console.print(f"[bold red]Failed:[/bold red] {item['url']} - {item['error']}")
    if result["failed"]:
        raise typer.Exit(1)

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
    from config.profiles import load_profile
    from src.pipeline import run_profile

    if not load_profile(username):
        console.print(f"[bold red]Profile @{username} not found. Add it first using 'profile add'[/bold red]")
        raise typer.Exit(1)

    try:
        result = run_profile(
            username,
            newer_than=newer_than,
            keep_media=keep_media,
            progress=console.print,
        )
    except ValueError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1)

    console.print(f"\n[bold green]Pipeline finished![/bold green] Processed {result['processed']} new posts.")
    console.print(f"Profile @{username} now has {result['total_processed']} processed and {result['failed']} failed.")


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to ask the knowledge base"),
    creator: Optional[str] = typer.Option(None, "--creator", "-c", help="Filter by specific Instagram creator"),
    mode: str = typer.Option(
        "grounded_plus",
        "--mode",
        help="'grounded_plus' (default: creator content + labeled general addendum) or 'strict' (creators only)",
    ),
    top_k: int = typer.Option(6, "--top-k", min=1, max=20, help="Number of posts to retrieve"),
    min_score: float = typer.Option(0.35, "--min-score", min=0.0, max=1.0, help="Minimum similarity score to trust a match"),
    history_file: Optional[Path] = typer.Option(
        None,
        "--history",
        help='JSON file with prior turns [{"role": "user|assistant", "content": "..."}] for follow-up questions',
    ),
):
    """Ask a question based on the indexed knowledge base."""
    console.print(f"[bold blue]Querying RAG Engine for:[/bold blue] [italic]'{question}'[/italic]")
    if creator:
        console.print(f"Filtered by creator: @{creator}")

    from src.pipeline import query_knowledge

    history_payload = None
    if history_file:
        import json

        try:
            history_payload = json.loads(history_file.read_text(encoding="utf-8"))
        except Exception as e:
            console.print(f"[bold red]Could not read history file:[/bold red] {e}")
            raise typer.Exit(1)

    try:
        result = query_knowledge(
            question, creator, top_k=top_k, min_score=min_score, mode=mode, history=history_payload
        )

        console.print("\n[bold green]=== Answer ===[/bold green]\n")
        console.print(result["answer"])
        if result.get("low_confidence"):
            console.print("[dim](low retrieval confidence - try rephrasing or indexing more content)[/dim]")

        if result["sources"]:
            cited_sources = [(i, s) for i, s in enumerate(result["sources"], start=1) if s.get("cited", True)]
            console.print("\n[bold yellow]Referenced Sources:[/bold yellow]")
            for i, src in cited_sources:
                score = f" (score: {src['score']:.4f})" if src.get("score") is not None else ""
                console.print(f" - [Source {i}] @{src['creator']}: {src['url']}{score}")
            uncited = len(result["sources"]) - len(cited_sources)
            if uncited:
                console.print(f"[dim]({uncited} retrieved source(s) not cited in the answer)[/dim]")
    except ValueError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Query failed:[/bold red] {e}")


@app.command()
def chat(
    creator: Optional[str] = typer.Option(None, "--creator", "-c", help="Filter by specific Instagram creator"),
    mode: str = typer.Option("grounded_plus", "--mode", help="'grounded_plus' or 'strict'"),
):
    """Interactive multi-turn conversation with the knowledge base.

    History is kept in this process only and sent to the engine on every
    turn (the API contract is stateless). Type 'exit' to leave.
    """
    from src.pipeline import query_knowledge

    history = []
    console.print("[bold blue]InstaRAG chat[/bold blue] — ask anything; 'exit' to quit.")
    while True:
        try:
            question = console.input("\n[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit", "salir"):
            break

        try:
            result = query_knowledge(question, creator, mode=mode, history=history)
        except ValueError as e:
            console.print(f"[bold red]{e}[/bold red]")
            continue
        except Exception as e:
            console.print(f"[bold red]Query failed:[/bold red] {e}")
            continue

        console.print(f"\n[bold green]Assistant:[/bold green]\n{result['answer']}")
        cited = [(i, s) for i, s in enumerate(result["sources"], start=1) if s.get("cited")]
        for i, src in cited:
            console.print(f"[dim][Source {i}] @{src['creator']}: {src['url']}[/dim]")

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": result["answer"]})

    console.print("[yellow]Chat closed.[/yellow]")


def main():
    app()


if __name__ == "__main__":
    main()
