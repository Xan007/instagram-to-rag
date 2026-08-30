"""Shared types and utilities for pipeline modules."""
import glob
import os
from typing import Any, Callable, Dict, List, Optional

from config.paths import RAW_DIR

Progress = Callable[[str], None]


def echo(message: str) -> None:
    print(message)


def download_with_ytdlp(url: str, pid: str, prefix: str = "saved") -> Optional[List[Dict[str, str]]]:
    """Download a reel/post with yt-dlp (video+audio merged via ffmpeg). Raises on failure."""
    from yt_dlp import YoutubeDL

    os.makedirs(RAW_DIR, exist_ok=True)
    outtmpl = os.path.join(RAW_DIR, f"{prefix}_{pid}.%(ext)s")
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 3,
        "concurrent_fragment_downloads": 4,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    if os.path.exists(filename):
        return [{"type": "video", "path": filename}]
    candidates = glob.glob(outtmpl.replace("%(ext)s", ".*"))
    return [{"type": "video", "path": candidates[0]}] if candidates else None
