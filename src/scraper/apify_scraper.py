import os
from typing import List, Dict, Generator, Any
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

class ApifyScraper:
    def __init__(self):
        api_key = os.getenv("APIFY_API_KEY")
        if not api_key:
            raise ValueError("APIFY_API_KEY environment variable is not set. Cannot use Apify filter.")
        self.client = ApifyClient(api_key)
        
    def get_posts_metadata(self, username: str, limit: int, skip_ids: List[str]) -> Generator[Dict[str, Any], None, None]:
        """
        Calls Apify Instagram Scraper actor to fetch posts metadata.
        """
        run_input = {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "posts",
            "resultsLimit": limit + len(skip_ids) # Fetch a bit more in case we skip many
        }
        
        print(f"Calling Apify Actor for @{username}... this might take a minute.")
        run = self.client.actor("apify/instagram-scraper").call(run_input=run_input)
        
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
                
            is_video = bool(item.get("isVideo")) or item.get("type") == "Video" or bool(item.get("videoUrl"))
            video_url = item.get("videoUrl") if is_video else None
            
            metadata = {
                "id": shortcode,
                "url": item.get("url", f"https://www.instagram.com/p/{shortcode}/"),
                "description": item.get("caption", ""),
                "hashtags": item.get("hashtags", []),
                "is_video": is_video,
                "video_url": video_url,
            }
            yield metadata
            count += 1
