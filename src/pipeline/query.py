"""Query the RAG knowledge base."""
from typing import Any, Dict, List, Optional


def query_knowledge(
    question: str,
    creator: Optional[str] = None,
    *,
    top_k: int = 6,
    min_score: float = 0.35,
    mode: str = "grounded_plus",
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Query the knowledge base; history enables stateless multi-turn chat."""
    from src.rag.query_engine import QueryEngine

    engine = QueryEngine()
    return engine.query(
        question=question,
        username=creator,
        top_k=top_k,
        min_score=min_score,
        mode=mode,
        history=history,
    )
