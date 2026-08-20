import typer
from rich.console import Console
from config.settings import load_settings, save_settings

app = typer.Typer(help="InstagramProfile2RAG - Extract knowledge from Instagram profiles.")
console = Console()

@app.command()
def config(
    interests: str = typer.Option(None, "--interests", help="Comma-separated interests (e.g. 'food, diet')"),
    max_posts: int = typer.Option(None, "--max-posts", help="Limit of posts to process"),
    audio_only: bool = typer.Option(None, "--audio-only", help="Process only audio"),
    engine: str = typer.Option(None, "--engine", help="'gemini' or 'local_whisper'"),
    embed_provider: str = typer.Option(None, "--embed-provider", help="'gemini' or 'local'")
):
    """Configure the pipeline settings."""
    settings = load_settings()
    
    updated = False
    if interests is not None:
        settings.interests = interests
        updated = True
    if max_posts is not None:
        settings.max_posts = max_posts
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
        console.print("[bold green]Settings updated successfully![/bold green]")
    
    console.print("\n[bold]Current Settings:[/bold]")
    for key, value in settings.model_dump().items():
        console.print(f"  {key}: {value}")


@app.command()
def run(username: str = typer.Argument(..., help="Instagram username to process")):
    """Run the pipeline to extract and index knowledge from a profile."""
    settings = load_settings()
    console.print(f"[bold blue]Starting pipeline for @{username}...[/bold blue]")
    console.print(f"Interests: {settings.interests}")
    console.print(f"Max posts: {settings.max_posts}")
    console.print(f"Engine: {settings.engine} | Embed Provider: {settings.embed_provider}")
    
    # TODO: Implement the scraper, filter, downloader, analyzer, and indexer logic here
    console.print("\n[yellow]Pipeline execution logic is not yet implemented.[/yellow]")


@app.command()
def query(question: str = typer.Argument(..., help="Question to ask the knowledge base")):
    """Ask a question based on the indexed knowledge."""
    console.print(f"[bold blue]Querying RAG for:[/bold blue] {question}")
    
    # TODO: Implement the query engine logic here
    console.print("\n[yellow]Query logic is not yet implemented.[/yellow]")


if __name__ == "__main__":
    app()
