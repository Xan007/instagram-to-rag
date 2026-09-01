import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from google import genai
from pinecone import Pinecone
from config.env import load_runtime_env
from src.llm.factory import LLMClientFactory
from src.rag.artifacts import get_artifact_system_prompt
from src.rag.conversation import (
    build_history_block,
    normalize_history,
)
from src.rag.hybrid import HybridRetriever

load_runtime_env()

logger = logging.getLogger(__name__)

INDEX_NAME = "instarag"
EMBEDDING_MODEL = "gemini-embedding-001"

_CITATION_RE = re.compile(r"Source\s*(\d+)", re.IGNORECASE)

DEFAULT_TOP_K = 6
DEFAULT_MIN_SCORE = 0.25
MAX_CAPTION_CHARS = 600

MODES = ("strict", "grounded_plus")


_LOW_CONFIDENCE_ANSWER = (
    "No encontré información directa sobre eso en los posts o reels guardados de los creadores. "
    "¿Quieres que busquemos sobre otro ejercicio, tema o receta?"
)

_NATURAL_ASSISTANT_PROMPT = """You are an intelligent, friendly, and expert AI assistant that responds like a natural, helpful chat conversation (WhatsApp style).
Your knowledge comes from the Instagram posts and reels provided in the context.

Conversation Guidelines:
1. Answer accurately, clearly, and concisely in the same language as the user's question.
2. Avoid robotic phrasing: do not say "Based on the provided documents" or "In the context given".
3. Cite your sources with [Source N] sparingly and naturally only when giving specific recommendations or data from creators. Do not spam or overuse citations on every single line.
4. NEVER invent, paste, or repeat URLs or posts that are not in the context.
5. Balanced proactivity: If the user asks a purely factual question, answer directly and concisely. If they ask for advice, planning, or routines, naturally offer 1 or 2 helpful follow-up suggestions or next steps without being pushy."""

_STRICT_RULES = _NATURAL_ASSISTANT_PROMPT + """


Strict Instructions:
- Answer the user's question using ONLY the provided context.
- If the context does not contain the answer, say clearly that you don't have that information from the creators' content."""

_GROUNDED_PLUS_RULES = _STRICT_RULES + """

Grounded Plus Extension:
- If general knowledge would clearly help the user, append ONE short additional block introduced exactly by:
---
General (no proviene de los creadores):
followed by 1-3 plain sentences of widely accepted knowledge on the topic.
- Never attribute anything in that final block to the creators or to any [Source N]; it must be clearly separate.
- If your grounded answer already fully covers the question, omit the extra block entirely."""


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

        self.llm = LLMClientFactory.get_client(stage="rag")
        self.rag_model = os.getenv("RAG_MODEL")
        self.hybrid_retriever = HybridRetriever()

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        import time
        for attempt in range(4):
            try:
                res = self.genai_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=text,
                    config=genai.types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
                )
                return res.embeddings[0].values
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota" in err_str:
                    wait_time = (attempt + 1) * 3
                    logger.warning("Gemini embedding rate limit; retrying in %ds (attempt %d/4)...", wait_time, attempt + 1)
                    time.sleep(wait_time)
                else:
                    logger.warning("Embedding generation error: %s", e)
                    break
        return None

    @staticmethod
    def build_context(matches: List[Dict[str, Any]], min_score: float) -> tuple:
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
                part += f"Caption: {caption[:MAX_CAPTION_CHARS]}\n"
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
        artifact_type: Optional[str] = None,
    ) -> str:
        artifact_prompt = get_artifact_system_prompt(artifact_type)
        if artifact_prompt:
            rules = artifact_prompt
        else:
            rules = _STRICT_RULES if mode == "strict" else _GROUNDED_PLUS_RULES

        conversation_section = ""
        if history_block:
            conversation_section = f"Conversation so far (for continuity only; do not repeat it):\n{history_block}\n\n"

        return f"""{rules}

{conversation_section}Context from Creator Posts:
{context}

User Question:
{question}"""

    @staticmethod
    def annotate_citations(answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cited = set(_CITATION_RE.findall(answer))
        return [{**src, "cited": str(i) in cited} for i, src in enumerate(sources, start=1)]

    def _condense_question(self, question: str, pairs: List[Tuple[str, str]]) -> str:
        if not pairs:
            return question.strip()

        history_text = "\n".join(f"{role.capitalize()}: {content}" for role, content in pairs)
        prompt = f"""Given the following conversation and a follow-up question, rephrase the follow-up question to be a standalone search query that contains all necessary context from previous turns. Do NOT answer the question. Only return the standalone question in the same language.

Conversation:
{history_text}

Follow-up Question: {question}

Standalone Question:"""

        try:
            condensed = self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                model=self.rag_model,
                temperature=0.0,
            )
            return condensed.strip() if condensed else question.strip()
        except Exception as e:
            logger.warning("Question condensation failed (%s). Using original question.", e)
            return question.strip()

    def query(
        self,
        question: str,
        creator: Optional[str] = None,
        post_ids: Optional[List[str]] = None,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
        mode: str = "grounded_plus",
        history: Optional[List[Dict[str, Any]]] = None,
        artifact_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")

        pairs = normalize_history(history)
        search_query = self._condense_question(question, pairs)

        filter_dict: Optional[Dict[str, Any]] = None
        if post_ids is not None:
            if not post_ids:
                return {
                    "answer": "Este grupo todavía no tiene posts indexados.",
                    "sources": [],
                    "mode": mode,
                }
            filter_dict = {"post_id": {"$in": post_ids}}
        elif creator:
            filter_dict = {"creator_username": {"$eq": creator}}

        query_vector = self._get_embedding(search_query)
        dense_matches = []
        if query_vector is not None:
            try:
                raw_k = max(top_k * 2, 10)
                results = self.index.query(
                    vector=query_vector,
                    top_k=raw_k,
                    include_metadata=True,
                    filter=filter_dict,
                )
                dense_matches = results.get("matches", [])
            except Exception as e:
                logger.warning("Pinecone query failed (%s); using local BM25 fallback.", e)


        hybrid_matches = self.hybrid_retriever.retrieve(
            query=search_query,
            pinecone_matches=dense_matches,
            creator=creator,
            post_ids=post_ids,
            top_k=top_k,
        )

        if not hybrid_matches:
            response = {
                "answer": "No encontré posts relevantes en la base de datos para responder a tu consulta.",
                "sources": [],
                "mode": mode,
            }
            if pairs:
                response["standalone_question"] = search_query
            return response

        context, sources, _dropped = self.build_context(hybrid_matches, min_score=min_score)
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
            artifact_type=artifact_type,
        )

        try:
            answer_text = self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                model=self.rag_model,
                temperature=0.3,
            )
            result = {
                "answer": answer_text,
                "sources": self.annotate_citations(answer_text, sources),
                "mode": mode,
                "artifact_type": artifact_type,
            }
            if pairs:
                result["standalone_question"] = search_query
            return result
        except Exception as e:
            logger.error("RAG generation failed: %s", e)
            return {
                "answer": f"Error al generar respuesta: {e}",
                "sources": sources,
                "mode": mode,
            }

