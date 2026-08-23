import os
import json
import time
from pathlib import Path
from typing import Dict, Any
from pinecone import Pinecone, ServerlessSpec
from google import genai
from config.env import load_runtime_env

load_runtime_env()

INDEX_NAME = "instarag"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 3072

class PineconeIndexer:
    def __init__(self, output_dir: str = "data/processed"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Google GenAI for Embeddings
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.genai_client = genai.Client(api_key=api_key)
        
        # Initialize Pinecone
        pinecone_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_key:
            raise ValueError("PINECONE_API_KEY environment variable is not set.")
        self.pc = Pinecone(api_key=pinecone_key)
        
        self._ensure_index_exists()
        self.index = self.pc.Index(INDEX_NAME)
        
    def _ensure_index_exists(self):
        """Ensures the serverless Pinecone index exists with the correct dimensions."""
        existing_indexes = [i.name for i in self.pc.list_indexes()]
        if INDEX_NAME not in existing_indexes:
            print(f"Creating Pinecone Index '{INDEX_NAME}' with dimension {EMBEDDING_DIM}...")
            self.pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
            time.sleep(5)
            
    def _get_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list:
        """Generates embeddings using Gemini embedding model with retry for rate limits."""
        for attempt in range(3):
            try:
                res = self.genai_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=text,
                    config=genai.types.EmbedContentConfig(task_type=task_type),
                )
                return res.embeddings[0].values
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"Embedding rate limit reached. Waiting 15s before retry ({attempt + 1}/3)...")
                    time.sleep(15)
                else:
                    raise e
        raise RuntimeError("Failed to generate embedding after 3 attempts.")

    def index_post(self, username: str, metadata: Dict[str, Any], extracted_text: str):
        """
        Embeds knowledge text, upserts into Pinecone, and saves local JSON backup.
        """
        post_id = metadata["id"]
        post_url = metadata["url"]
        
        # 1. Save local backup JSON
        document = {
            "id": post_id,
            "url": post_url,
            "username": username,
            "type": metadata.get("type", "Post"),
            "original_description": metadata.get("description", ""),
            "extracted_knowledge": extracted_text
        }
        file_path = self.output_dir / f"{post_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=4, ensure_ascii=False)
            
        # 2. Prepare text for embedding
        embed_input = f"Creator: @{username}\nURL: {post_url}\nKnowledge Summary:\n{extracted_text}"
        vector_values = self._get_embedding(embed_input)
        
        # 3. Upsert to Pinecone
        vector_id = f"{username}_{post_id}"
        # Keep metadata within 40KB limits
        meta = {
            "post_id": post_id,
            "username": username,
            "url": post_url,
            "type": metadata.get("type", "Post"),
            "original_description": metadata.get("description", "")[:1000],
            "extracted_knowledge": extracted_text[:8000]
        }
        
        self.index.upsert(
            vectors=[
                {
                    "id": vector_id,
                    "values": vector_values,
                    "metadata": meta
                }
            ]
        )
        print(f"-> Indexed @{username} post {post_id} into Pinecone & saved {file_path}")
