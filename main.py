import typer
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    console.print(f"[bold blue]Starting high-speed pipeline for @{username}...[/bold blue]")
    console.print(f"Specific Interests: {profile.interests}")
    console.print(f"Max posts: {profile.max_posts}")
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
    
    try:
        interest_filter = InterestFilter()
        analyzer = GeminiAnalyzer()
        indexer = PineconeIndexer()
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        console.print("Please check your .env file for GEMINI_API_KEY, PINECONE_API_KEY, etc.")
        raise typer.Exit(1)
        
    new_processed_ids = []
    
    try:
        # 1. Scrape metadata in batch
        console.print("\n[bold]Fetching post metadata...[/bold]")
        all_posts: List[Dict[str, Any]] = list(
            scraper.get_posts_metadata(username, profile.max_posts, profile.processed_ids)
        )
        console.print(f"Retrieved {len(all_posts)} new candidates to evaluate.")
        
        if not all_posts:
            console.print("[green]No new posts to process.[/green]")
            return
            
        # 2. High-speed batch interest filtering
        console.print(f"\n[bold]Running batch interest filtering on {len(all_posts)} posts...[/bold]")
        matching_ids = interest_filter.filter_batch(all_posts, profile.interests)
        matching_posts = [p for p in all_posts if p["id"] in matching_ids]
        console.print(f"[bold green]Filter matched {len(matching_posts)}/{len(all_posts)} relevant posts![/bold green]")
        
        if not matching_posts:
            console.print("[yellow]No posts matched the target interests.[/yellow]")
            return
            
        # 3. Parallel downloading & streaming to Gemini Analyzer
        console.print(f"\n[bold]Downloading media in parallel (4 workers) and streaming to Gemini...[/bold]")
        
        def download_task(post: Dict[str, Any]):
            media_items = post.get("media_items", [])
            downloaded = []
            if media_items:
                downloaded = downloader.download_media_items(media_items, post["id"])
            return post, downloaded

        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit download jobs
            future_to_post = {executor.submit(download_task, post): post for post in matching_posts}
            
            for future in as_completed(future_to_post):
                post, downloaded_files = future.result()
                post_id = post["id"]
                post_url = post["url"]
                
                console.print(f"\n[cyan]Processing Post ({post.get('type', 'Post')}): {post_url}[/cyan]")
                
                try:
                    # 4. Analyze
                    console.print("Analyzing content with Gemini...")
                    extracted_text = analyzer.extract_knowledge(downloaded_files, post.get("description", ""))
                    console.print(f"[green]Successfully extracted knowledge for {post_id}![/green]")
                    
                    # 5. Index into Pinecone
                    indexer.index_post(username, post, extracted_text)
                    
                    # Mark as processed
                    profile.processed_ids.append(post_id)
                    new_processed_ids.append(post_id)
                    
                    # Save profile progress immediately
                    save_profile(profile)
                    
                except Exception as e:
                    console.print(f"[red]Error analyzing post {post_id}:[/red] {e}")
                finally:
                    if downloaded_files:
                        downloader.cleanup_items(downloaded_files)
            
    except Exception as e:
        console.print(f"[bold red]An error occurred during pipeline execution:[/bold red] {e}")
        
    console.print(f"\n[bold green]Pipeline finished![/bold green] Processed {len(new_processed_ids)} new posts.")


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to ask the knowledge base"),
    creator: Optional[str] = typer.Option(None, "--creator", "-c", help="Filter by specific Instagram creator")
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


if __name__ == "__main__":
    app()
