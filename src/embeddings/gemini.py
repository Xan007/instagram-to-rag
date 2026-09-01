import logging
import os
import time
from typing import List, Optional
from google import genai
from config.env import load_runtime_env

load_runtime_env()
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 3072


class GeminiEmbeddingProvider:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.client = genai.Client(api_key=key)

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    def get_embedding(self, text: str, task_type: str = "query") -> List[float]:
        t_type = "RETRIEVAL_QUERY" if task_type == "query" else "RETRIEVAL_DOCUMENT"
        for attempt in range(4):
            try:
                res = self.client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=text,
                    config=genai.types.EmbedContentConfig(task_type=t_type),
                )
                return res.embeddings[0].values
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota" in err_str:
                    wait_time = (attempt + 1) * 3
                    logger.warning("Gemini embedding rate limit hit; retrying in %ds (attempt %d/4)...", wait_time, attempt + 1)
                    time.sleep(wait_time)
                else:
                    raise e
        raise RuntimeError("Gemini embedding quota exhausted after 4 attempts.")
