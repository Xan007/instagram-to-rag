import instaloader
from typing import List, Dict, Generator, Any

class LocalInstaloaderScraper:
    def __init__(self, ig_username: str = ""):
        self.L = instaloader.Instaloader(
            download_pictures=False,
            download_video_thumbnails=False,
            download_videos=False,  # We download videos later if they pass the filter
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )
        self.ig_username = ig_username
        if self.ig_username:
            try:
                self.L.load_session_from_file(self.ig_username)
                print(f"Loaded Instagram session for {self.ig_username}")
            except FileNotFoundError:
                print(f"Warning: No session file found for {self.ig_username}. Run 'instaloader -l {self.ig_username}' in your terminal to create one.")
            except Exception as e:
                print(f"Warning: Failed to load session for {self.ig_username}: {e}")
        
    def get_posts_metadata(self, username: str, limit: int, skip_ids: List[str]) -> Generator[Dict[str, Any], None, None]:
        """
        Yields metadata for posts from a profile, up to `limit`.
        Skips any post whose shortcode is in `skip_ids`.
        """
        try:
            profile = instaloader.Profile.from_username(self.L.context, username)
        except instaloader.exceptions.ProfileNotExistsException:
            raise ValueError(f"Profile {username} does not exist.")
        except instaloader.exceptions.ConnectionException as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                raise RuntimeError(
                    "Instagram blocked the request (429 Too Many Requests).\n"
                    "To fix this, you must log in. Run this in your terminal:\n"
                    "  instaloader -l YOUR_USERNAME\n"
                    "Then configure this app to use that session:\n"
                    "  uv run python main.py config --ig-username YOUR_USERNAME\n"
                )
            raise
            
        count = 0
        try:
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
        except instaloader.exceptions.ConnectionException as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                raise RuntimeError(
                    "Instagram blocked the request (429 Too Many Requests) while fetching posts.\n"
                    "To fix this, you must log in. Run this in your terminal:\n"
                    "  instaloader -l YOUR_USERNAME\n"
                    "Then configure this app to use that session:\n"
                    "  uv run python main.py config --ig-username YOUR_USERNAME\n"
                )
            raise
