import os
import time
from typing import Optional, List, Dict, Any
from pinecone import Pinecone
from google import genai
from dotenv import load_dotenv

load_dotenv()

INDEX_NAME = "ig-profile-rag"
EMBEDDING_MODEL = "gemini-embedding-001"

class QueryEngine:
    def __init__(self):
        # Initialize Google GenAI
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.genai_client = genai.Client(api_key=api_key)
        
        # Initialize Pinecone
        pinecone_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_key:
            raise ValueError("PINECONE_API_KEY environment variable is not set.")
        self.pc = Pinecone(api_key=pinecone_key)
        self.index = self.pc.Index(INDEX_NAME)
        
    def _get_embedding(self, text: str) -> list:
        """Generates query embedding."""
        res = self.genai_client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text
        )
        return res.embeddings[0].values

    def query(self, question: str, username: Optional[str] = None, top_k: int = 4) -> Dict[str, Any]:
        """
        Retrieves relevant context from Pinecone and generates a grounded response with Gemini.
        Always includes citations and original Instagram URLs.
        """
        # 1. Embed query
        query_vector = self._get_embedding(question)
        
        # 2. Query Pinecone
        filter_dict = {"username": {"$eq": username}} if username else None
        
        results = self.index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict
        )
        
        matches = results.get("matches", [])
        if not matches:
            return {
                "answer": "No relevant posts or knowledge found in the database to answer your question.",
                "sources": []
            }
            
        # 3. Format Context
        context_parts = []
        sources = []
        for idx, match in enumerate(matches):
            meta = match.get("metadata", {})
            post_url = meta.get("url", "Unknown URL")
            post_creator = meta.get("username", "Unknown")
            knowledge = meta.get("extracted_knowledge", "")
            
            context_parts.append(
                f"[Source {idx + 1}]\n"
                f"Creator: @{post_creator}\n"
                f"Post URL: {post_url}\n"
                f"Knowledge:\n{knowledge}\n"
            )
            sources.append({"creator": post_creator, "url": post_url, "score": match.get("score")})
            
        full_context = "\n---\n".join(context_parts)
        
        # 4. Generate Grounded Answer with Gemini
        prompt = f"""
You are a specialized AI assistant that answers questions based EXCLUSIVELY on knowledge extracted from Instagram creators.

Context from Creator Posts:
{full_context}

User Question:
{question}

Instructions:
1. Answer the user's question accurately and concisely using ONLY the provided context.
2. If the context does not contain the answer, say "Based on the creator's content, I don't have information about that."
3. At the end of every recommendation, fact, or recipe, ALWAYS cite and format the direct Instagram Post URL so the user can watch the original publication.
4. Format your response cleanly in Markdown.
"""
        for attempt in range(3):
            try:
                response = self.genai_client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=prompt
                )
                return {
                    "answer": response.text.strip(),
                    "sources": sources
                }
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"Rate limit reached on answer generation. Retrying in 10s ({attempt + 1}/3)...")
                    time.sleep(10)
                else:
                    raise e
                    
        return {
            "answer": "Failed to generate answer due to repeated rate limits. Please try again in a few seconds.",
            "sources": sources
        }
