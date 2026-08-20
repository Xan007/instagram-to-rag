import os
import re
from typing import List, Dict, Generator, Any, Optional
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

ACTOR_ID = "sones/instagram-posts-scraper-lowcost"
ACTOR_MAX_POSTS_PER_PROFILE = 500

MEDIA_TYPE_TO_POST_TYPE = {1: "Image", 2: "Video", 8: "Sidecar"}


def _extract_hashtags(text: str) -> List[str]:
    return re.findall(r"#(\w+)", text)


class ApifyScraper:
    def __init__(self, only_posts_newer_than: Optional[str] = None, verbose: bool = True):
        api_key = os.getenv("APIFY_API_KEY")
        if not api_key:
            raise ValueError("APIFY_API_KEY environment variable is not set. Cannot use Apify.")
        self.client = ApifyClient(api_key)
        self.only_posts_newer_than = only_posts_newer_than
        self.verbose = verbose

    def get_posts_metadata(self, username: str, limit: int, skip_ids: List[str]) -> Generator[Dict[str, Any], None, None]:
        skip_set = set(skip_ids)
        requested = min(limit + len(skip_set), ACTOR_MAX_POSTS_PER_PROFILE)

        run_input: Dict[str, Any] = {
            "usernames": [username],
            "postsPerProfile": requested,
            "proxy": {"useApifyProxy": True},
        }

        if self.only_posts_newer_than:
            run_input["newerThan"] = self.only_posts_newer_than

        print(f"[scrape] Calling {ACTOR_ID} for @{username}")
        print(f"[scrape] Requesting up to {requested} posts (target: {limit} new + {len(skip_set)} already processed)")
        if self.only_posts_newer_than:
            print(f"[scrape] Date filter: only posts newer than {self.only_posts_newer_than}")
        if limit + len(skip_set) > ACTOR_MAX_POSTS_PER_PROFILE:
            print(f"[scrape] WARNING: postsPerProfile is capped at {ACTOR_MAX_POSTS_PER_PROFILE} by the actor; "
                  f"may return fewer than {limit} new posts after skipping.")

        run = self.client.actor(ACTOR_ID).call(run_input=run_input)

        count = 0
        skipped_processed = 0
        no_media = 0
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
        for item in self.client.dataset(dataset_id).iterate_items():
            if count >= limit:
                break

            shortcode = item.get("code") or item.get("id", "")
            if not shortcode:
                continue

            if shortcode in skip_set:
                skipped_processed += 1
                if self.verbose:
                    print(f"[scrape] SKIP {shortcode}: already processed")
                continue

            media_type = item.get("media_type", 1)
            caption_obj = item.get("caption") or {}
            caption_text = caption_obj.get("text", "") if isinstance(caption_obj, dict) else str(caption_obj)

            media_items = []
            if media_type == 2:
                if item.get("video_url"):
                    media_items.append({"type": "video", "url": item.get("video_url")})
                elif item.get("image_url"):
                    media_items.append({"type": "image", "url": item.get("image_url")})
                    print(f"[scrape] WARNING {shortcode}: video has no video_url, falling back to thumbnail")
            elif media_type == 8:
                for child in item.get("carousel_media") or []:
                    if child.get("media_type") == 2:
                        if child.get("video_url"):
                            media_items.append({"type": "video", "url": child.get("video_url")})
                        elif child.get("image_url"):
                            media_items.append({"type": "image", "url": child.get("image_url")})
                            print(f"[scrape] WARNING {shortcode}: carousel video child has no video_url, falling back to thumbnail")
                    elif child.get("image_url"):
                        media_items.append({"type": "image", "url": child.get("image_url")})
            else:
                if item.get("image_url"):
                    media_items.append({"type": "image", "url": item.get("image_url")})

            if not media_items:
                no_media += 1

            if self.verbose:
                media_desc = ", ".join(m["type"] for m in media_items) or "NO MEDIA"
                post_type = MEDIA_TYPE_TO_POST_TYPE.get(media_type, "Image")
                print(f"[scrape] GOT {shortcode}: type={post_type}, media=[{media_desc}]")

            metadata = {
                "id": shortcode,
                "url": item.get("post_url", f"https://www.instagram.com/p/{shortcode}/"),
                "type": MEDIA_TYPE_TO_POST_TYPE.get(media_type, "Image"),
                "description": caption_text,
                "hashtags": _extract_hashtags(caption_text),
                "media_items": media_items,
            }
            yield metadata
            count += 1

        print(f"[scrape] Done: yielded {count} new post(s), skipped {skipped_processed} already processed, "
              f"{no_media} post(s) without media URLs.")