import instaloader
from typing import List, Dict, Generator, Any

class LocalInstaloaderScraper:
    def __init__(self):
        self.L = instaloader.Instaloader(
            download_pictures=False,
            download_video_thumbnails=False,
            download_videos=False,  # We download videos later if they pass the filter
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )
        
    def get_posts_metadata(self, username: str, limit: int, skip_ids: List[str]) -> Generator[Dict[str, Any], None, None]:
        """
        Yields metadata for posts from a profile, up to `limit`.
        Skips any post whose shortcode is in `skip_ids`.
        """
        try:
            profile = instaloader.Profile.from_username(self.L.context, username)
        except instaloader.exceptions.ProfileNotExistsException:
            raise ValueError(f"Profile {username} does not exist.")
            
        count = 0
        for post in profile.get_posts():
            if count >= limit:
                break
                
            if post.shortcode in skip_ids:
                continue
                
            metadata = {
                "id": post.shortcode,
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "description": post.caption if post.caption else "",
                "hashtags": post.caption_hashtags,
                "is_video": post.is_video,
                "video_url": post.video_url if post.is_video else None,
            }
            yield metadata
            count += 1
