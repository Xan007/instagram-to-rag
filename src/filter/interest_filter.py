import json
import logging
import os
import re
from typing import Dict, List, Set
from config.env import load_runtime_env
from src.llm.factory import LLMClientFactory

load_runtime_env()
logger = logging.getLogger(__name__)


class InterestFilter:
    def __init__(self):
        self.llm = LLMClientFactory.get_client(stage="filter")
        self.model = os.getenv("FILTER_MODEL")

    def filter_batch(self, posts: List[Dict], interests: str, chunk_size: int = 40) -> Set[str]:
        if not interests or not interests.strip():
            return {p["id"] for p in posts}

        matching_ids: Set[str] = set()

        for i in range(0, len(posts), chunk_size):
            chunk = posts[i:i + chunk_size]
            items_for_prompt = [
                {
                    "id": p["id"],
                    "caption": p.get("description", "")[:300],
                    "hashtags": p.get("hashtags", [])[:5],
                }
                for p in chunk
            ]

            prompt = f"""You are a batch content classifier for an Instagram knowledge base.
The user is ONLY interested in posts related to: "{interests}".

Review the following list of posts:
{json.dumps(items_for_prompt, ensure_ascii=False)}

Task:
Determine which post IDs match the user's interests or could contain relevant knowledge.
Respond with ONLY a valid JSON array of matching IDs, like:
["id1", "id2"]
If none match, respond with: []"""

            try:
                raw_response = self.llm.generate(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model,
                    temperature=0.0,
                )
                clean_text = raw_response.strip()
                if clean_text.startswith("```"):
                    clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
                    clean_text = re.sub(r"\n?```$", "", clean_text)
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
