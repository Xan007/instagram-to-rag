import os
import time
import warnings
from typing import Optional, List, Dict, Any
from pinecone import Pinecone
from google import genai
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv()

INDEX_NAME = "instarag"
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
        Retrieves relevant context from Pinecone and generates a grounded response with Gemini Chat API.
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
        seen_urls = set()
        for idx, match in enumerate(matches):
            meta = match.get("metadata", {})
            post_url = meta.get("url", "Unknown URL")
            post_creator = meta.get("username", "Unknown")
            knowledge = meta.get("extracted_knowledge", "")
            
            if post_url in seen_urls:
                continue
            seen_urls.add(post_url)
            
            context_parts.append(
                f"[Source {len(sources) + 1}]\n"
                f"Creator: @{post_creator}\n"
                f"Post URL: {post_url}\n"
                f"Knowledge:\n{knowledge}\n"
            )
            sources.append({"creator": post_creator, "url": post_url, "score": match.get("score")})
            
        full_context = "\n---\n".join(context_parts)
        
        # 4. Generate Grounded Answer with Gemini Chat API
        prompt = f"""
You are a specialized AI assistant that answers questions based EXCLUSIVELY on the knowledge extracted from Instagram posts provided in the context.

Context from Creator Posts:
{full_context}

User Question:
{question}

Instructions:
1. Answer the user's question accurately and concisely using ONLY the provided context.
2. If the context does not contain the answer, say "Based on the creator's content, I don't have information about that."
3. Cite your sources with [Source N] right after each fact or recommendation, using the source numbers from the context.
4. NEVER invent, paste, or repeat URLs or posts that are not in the context. Do not include a link more than once.
5. Write in the same language as the user's question.
6. Write as a natural plain-text chat message: no Markdown, no bold, no headers, no bullet lists, no asterisks.
7. Be concise and never repeat yourself: state each fact once, in a single sentence, and do not restate the same idea in different words.
"""
        for attempt in range(3):
            try:
                chat = self.genai_client.chats.create(model='gemini-3.5-flash-lite')
                response = chat.send_message(prompt)
                return {
                    "answer": response.text.strip(),
                    "sources": sources
                }
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                    print(f"Rate limit reached on answer generation. Retrying in 10s ({attempt + 1}/3)...")
                    time.sleep(10)
                else:
                    raise e
                    
        return {
            "answer": "Failed to generate answer due to repeated rate limits. Please try again in a few seconds.",
            "sources": sources
        }
