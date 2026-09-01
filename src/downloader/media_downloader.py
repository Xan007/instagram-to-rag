import logging
from pathlib import Path
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class MediaDownloader:
    def __init__(self, download_dir: str = "data/raw"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()

    def download_media_items(self, media_items: List[Dict[str, str]], post_id: str) -> List[Dict[str, str]]:
        downloaded: List[Dict[str, str]] = []
        for idx, item in enumerate(media_items):
            m_type = item.get("type", "image")
            m_url = item.get("url")
            if not m_url:
                continue

            ext = ".mp4" if m_type == "video" else ".jpg"
            filename = f"{post_id}_{idx}{ext}"
            file_path = self.download_dir / filename

            if not file_path.exists():
                try:
                    response = self.session.get(m_url, stream=True, timeout=30)
                    response.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                except Exception as e:
                    logger.error("Error downloading %s: %s", m_url, e)
                    continue

            downloaded.append({"type": m_type, "path": str(file_path.resolve())})

        return downloaded

    def cleanup_items(self, items: List[Dict[str, str]]) -> None:
        for item in items:
            p = Path(item["path"])
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def close(self) -> None:
        self.session.close()

