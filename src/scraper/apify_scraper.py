import os
from typing import List, Dict, Generator, Any
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

class ApifyScraper:
    def __init__(self):
        api_key = os.getenv("APIFY_API_KEY")
        if not api_key:
            raise ValueError("APIFY_API_KEY environment variable is not set. Cannot use Apify.")
        self.client = ApifyClient(api_key)
        
    def get_posts_metadata(self, username: str, limit: int, skip_ids: List[str]) -> Generator[Dict[str, Any], None, None]:
        """
        Calls Apify Instagram Post Scraper (apify/instagram-post-scraper) 
        which is faster, cheaper, and specifically designed for post metadata.
        """
        run_input = {
            "username": [username],
            "resultsLimit": limit + len(skip_ids),
            "skipPinnedPosts": False
        }
        
        print(f"Calling apify/instagram-post-scraper for @{username} (Limit: {limit})...")
        run = self.client.actor("apify/instagram-post-scraper").call(run_input=run_input)
        
        count = 0
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
        for item in self.client.dataset(dataset_id).iterate_items():
            if count >= limit:
                break
                
            shortcode = item.get("shortCode") or item.get("id", "")
            if not shortcode:
                continue
                
            if shortcode in skip_ids:
                continue
                
            post_type = item.get("type", "Image")
            media_items = []
            
            # Extract media items (video, image, carousel)
            if post_type == "Video" or bool(item.get("videoUrl")):
                if item.get("videoUrl"):
                    media_items.append({"type": "video", "url": item.get("videoUrl")})
            elif post_type == "Sidecar":
                child_posts = item.get("childPosts", [])
                if child_posts:
                    for child in child_posts:
                        if child.get("videoUrl"):
                            media_items.append({"type": "video", "url": child.get("videoUrl")})
                        elif child.get("displayUrl"):
                            media_items.append({"type": "image", "url": child.get("displayUrl")})
                elif item.get("images"):
                    for img_url in item.get("images"):
                        media_items.append({"type": "image", "url": img_url})
                elif item.get("displayUrl"):
                    media_items.append({"type": "image", "url": item.get("displayUrl")})
            else: # Image
                if item.get("displayUrl"):
                    media_items.append({"type": "image", "url": item.get("displayUrl")})
            
            metadata = {
                "id": shortcode,
                "url": item.get("url", f"https://www.instagram.com/p/{shortcode}/"),
                "type": post_type,
                "description": item.get("caption", ""),
                "hashtags": item.get("hashtags", []),
                "media_items": media_items,
            }
            yield metadata
            count += 1
