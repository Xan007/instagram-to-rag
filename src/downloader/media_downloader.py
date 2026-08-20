import os
import requests
from pathlib import Path

class MediaDownloader:
    def __init__(self, download_dir: str = "data/raw"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
    def download_video(self, video_url: str, post_id: str) -> str:
        """
        Downloads an MP4 video from a direct URL and saves it locally.
        Returns the absolute path to the downloaded file.
        """
        if not video_url:
            raise ValueError("No video URL provided.")
            
        file_path = self.download_dir / f"{post_id}.mp4"
        
        # If it already exists, return the path
        if file_path.exists():
            return str(file_path.absolute())
            
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return str(file_path.absolute())
        
    def cleanup(self, file_path: str):
        """Removes the downloaded file after processing."""
        path = Path(file_path)
        if path.exists():
            path.unlink()
