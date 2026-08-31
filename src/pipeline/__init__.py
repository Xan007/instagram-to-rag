"""Reusable pipeline operations shared by the CLI and the HTTP API."""
from src.pipeline._common import Progress, echo
from src.pipeline.run import scrape_profile
from src.pipeline.saved import import_user_saved_posts, process_saved
from src.pipeline.reel import add_reel
from src.pipeline.query import query_knowledge
from src.pipeline.group import populate_group_from_profile

__all__ = [
    "Progress",
    "echo",
    "scrape_profile",
    "import_user_saved_posts",
    "process_saved",
    "add_reel",
    "query_knowledge",
    "populate_group_from_profile",
]
