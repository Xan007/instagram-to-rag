import os
import requests
from pathlib import Path
from typing import List, Dict

class MediaDownloader:
    def __init__(self, download_dir: str = "data/raw"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()

    def download_media_items(self, media_items: List[Dict[str, str]], post_id: str) -> List[Dict[str, str]]:
        """
        Downloads media items (videos, images) and returns a list of local file dicts:
        [{"type": "video"|"image", "path": "/path/to/file"}]
        """
        downloaded = []
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
                    print(f"Error downloading {m_url}: {e}")
                    continue
                    
            downloaded.append({"type": m_type, "path": str(file_path.absolute())})
            
        return downloaded
        
    def cleanup_items(self, items: List[Dict[str, str]]):
        """Removes downloaded files after processing."""
        for item in items:
            p = Path(item["path"])
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
