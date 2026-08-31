import logging
import os
import re
import time
import warnings
from typing import Any, Dict, List, Optional
from pinecone import Pinecone
from google import genai
from config.env import load_runtime_env
from src.rag.conversation import (
    build_history_block,
    condense_question,
    normalize_history,
)

warnings.filterwarnings("ignore")
load_runtime_env()

logger = logging.getLogger(__name__)

INDEX_NAME = "instarag"
EMBEDDING_MODEL = "gemini-embedding-001"
GENERATION_MODEL = "gemini-2.5-flash"

_CITATION_RE = re.compile(r"\[Source (\d+)\]")

DEFAULT_TOP_K = 6
DEFAULT_MIN_SCORE = 0.35
MAX_CAPTION_CHARS = 600

MODES = ("strict", "grounded_plus")

_LOW_CONFIDENCE_ANSWER = (
    "No encontré contenido suficientemente relacionado con tu pregunta en la base de "
    "conocimiento de los creadores indexados. Prueba reformularla o consulta otro tema."
)

_STRICT_RULES = """
Instructions:
1. Answer the user's question accurately and concisely using ONLY the provided context.
2. If the context does not contain the answer, say exactly that you don't have that information from the creators' content.
3. Cite your sources with [Source N] right after each fact or recommendation, using the source numbers from the context.
4. NEVER invent, paste, or repeat URLs or posts that are not in the context. Do not include a link more than once.
5. Write in the same language as the user's question.
6. Write as a natural plain-text chat message: no Markdown, no bold, no headers, no bullet lists, no asterisks.
7. Be concise and never repeat yourself: state each fact once and do not restate the same idea in different words.
"""

_GROUNDED_PLUS_RULES = _STRICT_RULES + """
8. After your grounded answer, if general knowledge would clearly help the user (e.g. the posts cover the topic only partially), append ONE short additional block introduced exactly by:
---
General (no proviene de los creadores):
followed by 1-3 plain sentences of widely accepted knowledge on the topic.
9. Never attribute anything in that final block to the creators or to any [Source N]; it must be clearly separate.
10. If your grounded answer already fully covers the question, omit the extra block entirely.
"""


class QueryEngine:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.genai_client = genai.Client(api_key=api_key)

        pinecone_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_key:
            raise ValueError("PINECONE_API_KEY environment variable is not set.")
        self.pc = Pinecone(api_key=pinecone_key)
        self.index = self.pc.Index(INDEX_NAME)

    def _get_embedding(self, text: str) -> list:
        """Generates query embedding with retrieval-optimized task type."""
        res = self.genai_client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=genai.types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return res.embeddings[0].values

    @staticmethod
    def build_context(matches: List[Dict[str, Any]], min_score: float) -> tuple:
        """Filter matches by score, dedupe by URL and format prompt context."""
        context_parts = []
        sources = []
        seen_urls = set()
        dropped = 0
        for match in matches:
            meta = match.get("metadata", {})
            post_url = meta.get("url", "Unknown URL")
            post_creator = meta.get("creator_username", "Unknown")
            knowledge = meta.get("extracted_knowledge", "")
            caption = meta.get("original_description", "")

            if post_url in seen_urls:
                continue
            seen_urls.add(post_url)

            score = match.get("score")
            if min_score is not None and score is not None and score < min_score:
                dropped += 1
                continue

            part = f"[Source {len(sources) + 1}]\nCreator: @{post_creator}\nPost URL: {post_url}\n"
            if caption:
                part += f"Original caption: {caption[:MAX_CAPTION_CHARS]}\n"
            part += f"Knowledge:\n{knowledge}\n"
            context_parts.append(part)
            sources.append({"creator": post_creator, "url": post_url, "score": score})

        full_context = "\n---\n".join(context_parts)
        return full_context, sources, dropped

    @staticmethod
    def build_prompt(
        question: str,
        context: str,
        mode: str,
        history_block: str = "",
    ) -> str:
        rules = _STRICT_RULES if mode == "strict" else _GROUNDED_PLUS_RULES
        conversation_section = ""
        if history_block:
            conversation_section = f"""
Conversation so far (for continuity only; do not repeat it):
{history_block}
"""
        return f"""
You are a specialized AI assistant that answers questions based EXCLUSIVELY on the knowledge extracted from Instagram posts provided in the context.
{conversation_section}
Context from Creator Posts:
{context}

User Question:
{question}
{rules}"""

    @staticmethod
    def annotate_citations(answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cited = set(_CITATION_RE.findall(answer))
        return [{**src, "cited": str(i) in cited} for i, src in enumerate(sources, start=1)]

    def query(
        self,
        question: str,
        creator: Optional[str] = None,
        post_ids: Optional[List[str]] = None,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
        mode: str = "grounded_plus",
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Query RAG engine, filtering optionally by creator or by post_ids (for a specific group)."""
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")

        pairs = normalize_history(history)
        search_query = condense_question(self.genai_client, GENERATION_MODEL, question, pairs)
        query_vector = self._get_embedding(search_query)

        filter_dict: Optional[Dict[str, Any]] = None
        if post_ids is not None:
            if not post_ids:
                return {
                    "answer": "This group does not have any posts indexed yet.",
                    "sources": [],
                    "mode": mode,
                }
            filter_dict = {"post_id": {"$in": post_ids}}
        elif creator:
            filter_dict = {"creator_username": {"$eq": creator}}

        results = self.index.query(
            vector=query_vector,
            top_k=max(1, int(top_k)),
            include_metadata=True,
            filter=filter_dict,
        )

        matches = results.get("matches", [])
        if not matches:
            response = {
                "answer": "No relevant posts or knowledge found in the database to answer your question.",
                "sources": [],
                "mode": mode,
            }
            if pairs:
                response["standalone_question"] = search_query
            return response

        context, sources, _dropped = self.build_context(matches, min_score=min_score)
        if not context:
            return {
                "answer": _LOW_CONFIDENCE_ANSWER,
                "sources": [],
                "mode": mode,
                "low_confidence": True,
                **({"standalone_question": search_query} if pairs else {}),
            }

        prompt = self.build_prompt(
            question,
            context,
            mode,
            history_block=build_history_block(pairs),
        )
        for attempt in range(3):
            try:
                chat = self.genai_client.chats.create(model=GENERATION_MODEL)
                response = chat.send_message(prompt)
                result = {
                    "answer": response.text.strip(),
                    "sources": self.annotate_citations(response.text.strip(), sources),
                    "mode": mode,
                }
                if pairs:
                    result["standalone_question"] = search_query
                return result
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str:
                    logger.info("Rate limit reached. Retrying in 10s (%d/3)...", attempt + 1)
                    time.sleep(10)
                else:
                    raise e

        return {
            "answer": "Failed to generate answer due to repeated rate limits.",
            "sources": sources,
            "mode": mode,
        }
