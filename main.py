from pathlib import Path
from typing import List, Optional
from rich.console import Console
import typer

app = typer.Typer(
    name="instarag",
    help="instarag -- Multi-account Instagram RAG & Agent Knowledge Base.",
    add_completion=False,
)

user_app = typer.Typer(help="Manage local user accounts.")
app.add_typer(user_app, name="user")

profile_app = typer.Typer(help="Manage and scrape global Instagram creator profiles.")
app.add_typer(profile_app, name="profile")

group_app = typer.Typer(help="Manage scoped RAG agents / collections (Groups) and sharing.")
app.add_typer(group_app, name="group")

saved_app = typer.Typer(help="Import and process Instagram saved posts per user.")
app.add_typer(saved_app, name="saved")

console = Console()


def _get_active_user(user_opt: Optional[str]) -> str:
    from config.users import list_users, resolve_user
    user = resolve_user(user_opt)
    if not user:
        all_users = list_users()
        if len(all_users) == 1:
            return all_users[0].id
        console.print("[bold red]User not specified and no default found. Use '--user <username>' or set INSTARAG_USER env var.[/bold red]")
        raise typer.Exit(1)
    return user.id


@user_app.command("create")
def user_create(username: str = typer.Argument(..., help="Username for the new account")):
    from config.users import create_user, load_user
    if load_user(username):
        console.print(f"[bold yellow]User '{username}' already exists.[/bold yellow]")
        return
    user = create_user(username)
    console.print(f"[bold green]User '{user.username}' created successfully (ID: {user.id}).[/bold green]")


@user_app.command("list")
def user_list():
    from config.users import list_users
    users = list_users()
    if not users:
        console.print("[yellow]No users found. Create one with 'user create <username>'.[/yellow]")
        return
    console.print("[bold blue]Registered Users:[/bold blue]")
    for u in users:
        console.print(f"  - [bold]{u.username}[/bold] (ID: {u.id})")


@profile_app.command("add")
def profile_add(
    username: str = typer.Argument(..., help="Instagram creator username"),
):
    from config.ig_profiles import IGProfileInfo, load_ig_profile, save_ig_profile
    p = load_ig_profile(username)
    if not p:
        save_ig_profile(IGProfileInfo(username=username))
        console.print(f"[bold green]Registered creator profile @{username} globally.[/bold green]")
    else:
        console.print(f"[bold yellow]Profile @{username} is already registered.[/bold yellow]")


@profile_app.command("scrape")
def profile_scrape_cmd(
    username: str = typer.Argument(..., help="Instagram creator username"),
    max_posts: int = typer.Option(200, "--max-posts", help="Max posts to scrape"),
    newer_than: Optional[str] = typer.Option(None, "--newer-than", help="Only scrape newer than date"),
    keep_media: bool = typer.Option(False, "--keep-media", help="Keep media files"),
):
    from src.pipeline import scrape_profile
    try:
        res = scrape_profile(
            username=username,
            newer_than=newer_than,
            max_posts=max_posts,
            keep_media=keep_media,
            progress=console.print,
        )
        console.print(f"\n[bold green]Finished scraping @{username}![/bold green] Processed: {res['processed']}, Total Indexed: {res['total_indexed']}")
    except Exception as e:
        console.print(f"[bold red]Scrape failed:[/bold red] {e}")
        raise typer.Exit(1)


@profile_app.command("update")
def profile_update_cmd(
    username: str = typer.Argument(..., help="Instagram creator username"),
    keep_media: bool = typer.Option(False, "--keep-media", help="Keep media files"),
):
    from datetime import datetime, timezone
    from config.ig_profiles import load_ig_profile
    from src.pipeline import scrape_profile

    p = load_ig_profile(username)
    effective_newer = None
    if p and p.last_scraped_at:
        dt = datetime.fromtimestamp(p.last_scraped_at, tz=timezone.utc)
        effective_newer = dt.strftime("%Y-%m-%d")
        console.print(f"[bold blue]Auto date filter:[/bold blue] {effective_newer}")

    try:
        res = scrape_profile(
            username=username,
            newer_than=effective_newer,
            keep_media=keep_media,
            progress=console.print,
        )
        console.print(f"\n[bold green]Update completed![/bold green] +{res['processed']} new posts indexed.")
    except Exception as e:
        console.print(f"[bold red]Update failed:[/bold red] {e}")
        raise typer.Exit(1)


@profile_app.command("list")
def profile_list():
    from config.ig_profiles import list_ig_profiles
    profiles = list_ig_profiles()
    if not profiles:
        console.print("[yellow]No profiles registered yet.[/yellow]")
        return
    console.print("[bold blue]Instagram Creator Profiles (Global):[/bold blue]")
    for p in profiles:
        console.print(f"  - @[bold]{p.username}[/bold] | Posts scraped: {p.total_posts_scraped} | Last run: {p.last_run_at or 'never'}")


@group_app.command("create")
def group_create_cmd(
    name: str = typer.Argument(..., help="Name of the RAG agent/group"),
    description: str = typer.Option("", "--desc", "-d", help="Description of the group agent"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Username owner"),
):
    from config.groups import create_group, load_group_by_name
    uid = _get_active_user(user)
    if load_group_by_name(uid, name):
        console.print(f"[bold yellow]Group '{name}' already exists for this account.[/bold yellow]")
        return
    g = create_group(uid, name, description)
    console.print(f"[bold green]Created RAG Agent group '{g.name}' (ID: {g.id}).[/bold green]")


@group_app.command("list")
def group_list_cmd(
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Username"),
):
    from config.groups import list_groups_for_user
    uid = _get_active_user(user)
    groups = list_groups_for_user(uid)
    if not groups:
        console.print("[yellow]No groups found. Create one with 'group create <name>'.[/yellow]")
        return
    console.print("[bold blue]Your RAG Agent Groups:[/bold blue]")
    for g in groups:
        owner_tag = "[green](owner)[/green]" if g.owner_id == uid else "[yellow](shared)[/yellow]"
        console.print(f"  - [bold]{g.name}[/bold] {owner_tag} | Posts: {g.post_count} | Desc: {g.description or '-'}")


@group_app.command("add-from-profile")
def group_add_from_profile_cmd(
    group_name: str = typer.Argument(..., help="Target group name"),
    creator: str = typer.Argument(..., help="Creator Instagram username"),
    interests: Optional[str] = typer.Option(None, "--interests", "-i", help="Filter posts by topic/interests before adding"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Account username"),
):
    from src.pipeline import populate_group_from_profile
    uid = _get_active_user(user)
    try:
        res = populate_group_from_profile(uid, group_name, creator, interests=interests, progress=console.print)
        console.print(f"[bold green]Successfully added {res['added']} posts to group '{group_name}'![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Failed to populate group:[/bold red] {e}")
        raise typer.Exit(1)


@group_app.command("add-post")
def group_add_post_cmd(
    group_name: str = typer.Argument(..., help="Group name"),
    url_or_id: str = typer.Argument(..., help="Post URL or shortcode ID"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Account username"),
):
    from config.groups import add_post_to_group, load_group_by_name
    from src.pipeline import add_reel

    uid = _get_active_user(user)
    group = load_group_by_name(uid, group_name)
    if not group:
        console.print(f"[bold red]Group '{group_name}' not found.[/bold red]")
        raise typer.Exit(1)

    if url_or_id.startswith("http"):
        add_reel([url_or_id], group_id=group.id, progress=console.print)
    else:
        add_post_to_group(group.id, url_or_id)
        console.print(f"[bold green]Added post {url_or_id} to group '{group_name}'.[/bold green]")


@group_app.command("share")
def group_share_cmd(
    group_name: str = typer.Argument(..., help="Group name to share"),
    target_user: str = typer.Argument(..., help="Target username to grant access"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Owner username"),
):
    from config.groups import load_group_by_name, share_group
    from config.users import load_user

    uid = _get_active_user(user)
    group = load_group_by_name(uid, group_name)
    if not group or group.owner_id != uid:
        console.print(f"[bold red]You are not the owner of group '{group_name}'.[/bold red]")
        raise typer.Exit(1)

    t_user = load_user(target_user)
    if not t_user:
        console.print(f"[bold red]Target user '{target_user}' does not exist.[/bold red]")
        raise typer.Exit(1)

    if share_group(group.id, t_user.id):
        console.print(f"[bold green]Shared group '{group_name}' with '{target_user}'.[/bold green]")
    else:
        console.print(f"[yellow]Group was already shared with '{target_user}'.[/yellow]")


@saved_app.command("import")
def saved_import_cmd(
    path: Path = typer.Argument(..., help="Path to your Instagram zip export or saved_posts.json"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Account username"),
):
    from src.pipeline import import_user_saved_posts
    uid = _get_active_user(user)
    try:
        res = import_user_saved_posts(uid, path)
        console.print(f"[bold green]Imported {res['total']} saved posts ({res['new_saved']} new bookmarks)![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Import failed:[/bold red] {e}")
        raise typer.Exit(1)


@saved_app.command("process")
def saved_process_cmd(
    limit: Optional[int] = typer.Option(None, "--limit", help="Max pending posts to process"),
    caption_only: bool = typer.Option(False, "--caption-only", help="Skip media download"),
    workers: int = typer.Option(4, "--workers", help="Worker count"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Account username"),
):
    from src.pipeline import process_saved
    uid = _get_active_user(user)
    try:
        res = process_saved(uid, limit=limit, caption_only=caption_only, workers=workers, progress=console.print)
        console.print(f"\n[bold green]Finished processing saved posts![/bold green] Processed: {res['processed']}, Already Indexed: {res['already_indexed']}, Failed: {res['failed']}")
    except Exception as e:
        console.print(f"[bold red]Processing failed:[/bold red] {e}")
        raise typer.Exit(1)


@app.command("query")
def query_cmd(
    question: str = typer.Argument(..., help="Question to ask"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Scope question to a specific RAG agent group"),
    creator: Optional[str] = typer.Option(None, "--creator", "-c", help="Scope question to a creator"),
    mode: str = typer.Option("grounded_plus", "--mode", help="'grounded_plus' or 'strict'"),
    artifact: Optional[str] = typer.Option(None, "--artifact", "-a", help="'workout_plan', 'recipe_book', or 'grocery_list'"),
    export: Optional[str] = typer.Option(None, "--export", "-o", help="Export to file (.md or .pdf)"),
    top_k: int = typer.Option(6, "--top-k", help="Top matches"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Account username"),
):
    from src.pipeline import query_knowledge
    from src.rag.artifacts import export_artifact
    uid = None
    if group:
        uid = _get_active_user(user)

    try:
        res = query_knowledge(
            question,
            creator=creator,
            group_name=group,
            user_id=uid,
            top_k=top_k,
            mode=mode,
            artifact_type=artifact,
        )
        console.print("\n[bold green]=== Answer ===[/bold green]\n")
        console.print(res["answer"])
        if res.get("sources"):
            console.print("\n[bold yellow]Sources:[/bold yellow]")
            for i, s in enumerate(res["sources"], 1):
                if s.get("cited", True):
                    console.print(f" - [Source {i}] @{s['creator']}: {s['url']}")

        if export:
            title = artifact.replace("_", " ").title() if artifact else "InstaRAG Query Export"
            exported_path = export_artifact(
                content=res["answer"],
                output_path=export,
                title=title,
                sources=res.get("sources"),
            )
            console.print(f"\n[bold green]✓ Artifact exported successfully to:[/bold green] [cyan]{exported_path}[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Query failed:[/bold red] {e}")
        raise typer.Exit(1)




@app.command("chat")
def chat_cmd(
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Scope chat to a specific RAG agent group"),
    creator: Optional[str] = typer.Option(None, "--creator", "-c", help="Scope chat to a creator"),
    mode: str = typer.Option("grounded_plus", "--mode", help="'grounded_plus' or 'strict'"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Account username"),
):
    from src.pipeline import query_knowledge
    uid = None
    if group:
        uid = _get_active_user(user)

    history = []
    scope_desc = f"Group '{group}'" if group else (f"@{creator}" if creator else "Global Knowledge")
    console.print(f"[bold blue]InstaRAG Chat ({scope_desc})[/bold blue] — type 'exit' to quit.")

    while True:
        try:
            q = console.input("\n[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("exit", "quit", "salir"):
            break

        try:
            res = query_knowledge(q, creator=creator, group_name=group, user_id=uid, mode=mode, history=history)
            console.print(f"\n[bold green]Assistant:[/bold green]\n{res['answer']}")
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": res["answer"]})
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


def main():
    from storage.db import init_db
    init_db()
    app()


if __name__ == "__main__":
    main()

