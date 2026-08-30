"""Reusable pipeline operations shared by the CLI and the HTTP API.

Every public function accepts an optional ``progress`` callback used to
report step-by-step messages; callers decide how to render them (rich
console in the CLI, job logs in the API).
"""
from src.pipeline._common import Progress, echo
from src.pipeline.run import run_profile
from src.pipeline.saved import process_saved
from src.pipeline.reel import add_reel
from src.pipeline.query import query_knowledge

__all__ = [
    "Progress",
    "echo",
    "run_profile",
    "process_saved",
    "add_reel",
    "query_knowledge",
]
