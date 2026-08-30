import json
import logging
import os
import time
import warnings
from typing import List, Dict, Set
from google import genai
from config.env import load_runtime_env

warnings.filterwarnings("ignore")
load_runtime_env()

logger = logging.getLogger(__name__)

FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.6-flash"
]

class InterestFilter:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Cannot use Gemini filter.")
        self.client = genai.Client(api_key=api_key)
        
    def _call_with_fallback(self, prompt: str) -> str:
        """Tries models in order with exponential backoff on 503/429 errors."""
        last_error = None
        for model_name in FALLBACK_MODELS:
            for attempt in range(2):
                try:
                    chat = self.client.chats.create(model=model_name)
                    response = chat.send_message(prompt)
                    return response.text.strip()
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    if "503" in err_str or "UNAVAILABLE" in err_str:
                        logger.info("Model %s is experiencing 503 high demand. Trying next model...", model_name)
                        break
                    elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        logger.info("Rate limit on %s. Waiting 10s...", model_name)
                        time.sleep(10)
                    else:
                        break
        raise RuntimeError(f"All fallback models failed for filtering: {last_error}")

    def filter_batch(self, posts: List[Dict], interests: str, chunk_size: int = 40) -> Set[str]:
        """
        Batches post evaluation to dramatically speed up execution and reduce API calls.
        Returns a set of matching post IDs.
        """
        if not interests.strip():
            return {p["id"] for p in posts}
            
        matching_ids: Set[str] = set()
        
        for i in range(0, len(posts), chunk_size):
            chunk = posts[i:i + chunk_size]
            items_for_prompt = [
                {
                    "id": p["id"],
                    "caption": p.get("description", "")[:300],
                    "hashtags": p.get("hashtags", [])[:5]
                }
                for p in chunk
            ]
            
            prompt = f"""
You are a batch content classifier for an Instagram knowledge base.
The user is ONLY interested in posts related to: "{interests}".

Review the following list of posts:
{json.dumps(items_for_prompt, ensure_ascii=False)}

Task:
Determine which post IDs match the user's interests or could contain relevant knowledge.
Respond with ONLY a valid JSON array of matching IDs, like:
["id1", "id2"]
If none match, respond with: []
"""
            try:
                raw_response = self._call_with_fallback(prompt)
                clean_text = raw_response.strip()
                if clean_text.startswith("```"):
                    clean_text = clean_text.split("```")[1]
                    if clean_text.startswith("json"):
                        clean_text = clean_text[4:]
                clean_text = clean_text.strip()
                
                accepted_ids = json.loads(clean_text)
                if isinstance(accepted_ids, list):
                    for aid in accepted_ids:
                        matching_ids.add(str(aid))
            except Exception as e:
                logger.warning("Batch filter failed on chunk (%s). Defaulting to include all chunk items.", e)
                for p in chunk:
                    matching_ids.add(p["id"])
                    
        return matching_ids
