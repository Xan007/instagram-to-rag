import logging
import os
import time
from typing import Any, Dict, List, Optional

from google import genai
from pinecone import Pinecone, ServerlessSpec
from config.env import load_runtime_env

load_runtime_env()

logger = logging.getLogger(__name__)

INDEX_NAME = "instarag"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 3072
MAX_CAPTION_CHARS = 1000
MAX_KNOWLEDGE_CHARS = 8000


class PineconeIndexer:
    def __init__(self, gemini_api_key: Optional[str] = None, pinecone_api_key: Optional[str] = None):
        api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.genai_client = genai.Client(api_key=api_key)

        p_key = pinecone_api_key or os.getenv("PINECONE_API_KEY")
        if not p_key:
            raise ValueError("PINECONE_API_KEY environment variable is not set.")
        self.pc = Pinecone(api_key=p_key)

        self._ensure_index_exists()
        self.index = self.pc.Index(INDEX_NAME)

    def _ensure_index_exists(self) -> None:
        existing = [i.name for i in self.pc.list_indexes()]
        if INDEX_NAME not in existing:
            logger.info("Creating Pinecone index '%s' (dim=%d)...", INDEX_NAME, EMBEDDING_DIM)
            self.pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            while not self.pc.describe_index(name=INDEX_NAME).status.ready:
                logger.info("Waiting for index to be ready...")
                time.sleep(2)

    def _get_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        for attempt in range(3):
            try:
                res = self.genai_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=text,
                    config=genai.types.EmbedContentConfig(task_type=task_type),
                )
                return res.embeddings[0].values
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    logger.info("Embedding rate limit; retrying in 15s (%d/3)...", attempt + 1)
                    time.sleep(15)
                else:
                    raise
        raise RuntimeError("Failed to generate embedding after 3 attempts.")

    def index_post(
        self,
        post_id: str,
        url: str,
        creator_username: str,
        post_type: str,
        description: str,
        extracted_text: str,
    ) -> None:
        from storage.db import get_session
        from storage.models import Post
        import storage.repositories as repo

        indexed_at = time.time()

        db = get_session()
        try:
            post = Post(
                id=post_id,
                url=url,
                creator_username=creator_username,
                type=post_type,
                description=description,
                extracted_knowledge=extracted_text,
                indexed_at=indexed_at,
            )
            repo.upsert_post(db, post)
        finally:
            db.close()

        embed_input = (
            f"Creator: @{creator_username}\n"
            f"URL: {url}\n"
            f"Knowledge Summary:\n{extracted_text}"
        )
        vector_values = self._get_embedding(embed_input)

        vector_id = f"{creator_username}_{post_id}" if creator_username else post_id
        meta = {
            "post_id": post_id,
            "creator_username": creator_username or "",
            "url": url,
            "type": post_type,
            "original_description": description[:MAX_CAPTION_CHARS],
            "extracted_knowledge": extracted_text[:MAX_KNOWLEDGE_CHARS],
        }
        self.index.upsert(vectors=[{"id": vector_id, "values": vector_values, "metadata": meta}])
        logger.info("Indexed post %s (@%s) -> Pinecone + DB", post_id, creator_username)

    def delete_post(self, post_id: str, creator_username: str = "") -> None:
        vector_id = f"{creator_username}_{post_id}" if creator_username else post_id
        self.index.delete(ids=[vector_id])
        logger.info("Deleted vector %s from Pinecone", vector_id)

