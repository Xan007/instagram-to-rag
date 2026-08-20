import typer
from rich.console import Console
from config.settings import load_settings, save_settings
from config.profiles import ProfileConfig, load_profile, save_profile, list_profiles

app = typer.Typer(help="InstagramProfile2RAG - Extract knowledge from Instagram profiles.")
profile_app = typer.Typer(help="Manage Instagram profiles.")
app.add_typer(profile_app, name="profile")

console = Console()

@app.command()
def config(
    audio_only: bool = typer.Option(None, "--audio-only", help="Process only audio globally"),
    engine: str = typer.Option(None, "--engine", help="'gemini' or 'local_whisper'"),
    embed_provider: str = typer.Option(None, "--embed-provider", help="'gemini' or 'local'"),
    ig_username: str = typer.Option(None, "--ig-username", help="Your Instagram username to load session and prevent 429 blocks"),
    scraper_engine: str = typer.Option(None, "--scraper-engine", help="'apify' or 'instaloader'")
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
    interests: str = typer.Option(..., "--interests", help="Comma-separated interests (e.g. 'food, diet')"),
    max_posts: int = typer.Option(50, "--max-posts", help="Limit of posts to process per run")
):
    """Add or update an Instagram profile to track."""
    profile = load_profile(username)
    if profile:
        profile.interests = interests
        profile.max_posts = max_posts
        console.print(f"[bold yellow]Updated existing profile @{username}[/bold yellow]")
    else:
        profile = ProfileConfig(username=username, interests=interests, max_posts=max_posts)
        console.print(f"[bold green]Added new profile @{username}[/bold green]")
        
    save_profile(profile)
    console.print(f"Interests: {profile.interests} | Max posts: {profile.max_posts}")


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
            console.print(f"  - @[bold]{p.username}[/bold]: {p.interests} (Processed: {len(p.processed_ids)} posts)")


@app.command()
def run(username: str = typer.Argument(..., help="Instagram username to process")):
    """Run the pipeline to extract and index knowledge from a profile."""
    profile = load_profile(username)
    if not profile:
        console.print(f"[bold red]Profile @{username} not found. Add it first using 'profile add'[/bold red]")
        raise typer.Exit(1)
        
    settings = load_settings()
    console.print(f"[bold blue]Starting pipeline for @{username}...[/bold blue]")
    console.print(f"Specific Interests: {profile.interests}")
    console.print(f"Global Engine: {settings.engine} | Embed Provider: {settings.embed_provider}")
    console.print(f"Scraper Engine: {settings.scraper_engine}")
    
    # Initialize components
    from src.scraper.local_instaloader import LocalInstaloaderScraper
    from src.scraper.apify_scraper import ApifyScraper
    from src.filter.interest_filter import InterestFilter
    from src.downloader.media_downloader import MediaDownloader
    from src.analyzer.gemini_analyzer import GeminiAnalyzer
    from src.indexer.pinecone_indexer import PineconeIndexer
    
    if settings.scraper_engine == "apify":
        scraper = ApifyScraper()
    else:
        scraper = LocalInstaloaderScraper(settings.ig_username)
        
    downloader = MediaDownloader()
    indexer = PineconeIndexer()
    
    try:
        interest_filter = InterestFilter()
        analyzer = GeminiAnalyzer()
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        console.print("Please set GEMINI_API_KEY in your .env file.")
        raise typer.Exit(1)
        
    new_processed_ids = []
    
    try:
        # 1. Scrape metadata
        console.print("\n[bold]Fetching posts...[/bold]")
        post_generator = scraper.get_posts_metadata(username, profile.max_posts, profile.processed_ids)
        
        for metadata in post_generator:
            post_id = metadata["id"]
            console.print(f"\n[cyan]Evaluating Post: {metadata['url']}[/cyan]")
            
            # 2. Filter based on description/hashtags
            decision = interest_filter.evaluate(metadata["description"], metadata["hashtags"], profile.interests)
            console.print(f"Filter Decision: [bold]{decision}[/bold]")
            
            if decision == "NO":
                console.print("Skipping post (did not match interests).")
                continue
                
            if not metadata["is_video"] or not metadata["video_url"]:
                console.print("Post is not a video or has no URL. Skipping for now (only reels supported currently).")
                continue
                
            # 3. Download
            console.print("Downloading media...")
            try:
                video_path = downloader.download_video(metadata["video_url"], post_id)
            except Exception as e:
                console.print(f"[red]Failed to download video:[/red] {e}")
                continue
                
            # 4. Analyze
            console.print("Analyzing video with Gemini...")
            try:
                extracted_text = analyzer.extract_knowledge(video_path, metadata["description"])
                console.print(f"[green]Successfully extracted knowledge![/green]")
            except Exception as e:
                console.print(f"[red]Failed to analyze video:[/red] {e}")
                continue
            finally:
                downloader.cleanup(video_path)
                
            # 5. Index
            indexer.index_post(username, metadata, extracted_text)
            
            # Mark as processed
            profile.processed_ids.append(post_id)
            new_processed_ids.append(post_id)
            
            # Save profile progress immediately so we don't lose it if it crashes
            save_profile(profile)
            
    except Exception as e:
        console.print(f"[bold red]An error occurred during pipeline execution:[/bold red] {e}")
        
    console.print(f"\n[bold green]Pipeline finished![/bold green] Processed {len(new_processed_ids)} new posts.")


@app.command()
def query(question: str = typer.Argument(..., help="Question to ask the knowledge base")):
    """Ask a question based on the indexed knowledge."""
    console.print(f"[bold blue]Querying RAG for:[/bold blue] {question}")
    
    # TODO: Implement the query engine logic here
    console.print("\n[yellow]Query logic is not yet implemented.[/yellow]")


if __name__ == "__main__":
    app()
