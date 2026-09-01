from typing import Any, Dict, List, Optional
from config.groups import get_post_ids_in_group, load_group_by_name, user_can_access_group


def query_knowledge(
    question: str,
    creator: Optional[str] = None,
    group_name: Optional[str] = None,
    user_id: Optional[str] = None,
    *,
    top_k: int = 6,
    min_score: float = 0.25,
    mode: str = "grounded_plus",
    history: Optional[List[Dict[str, Any]]] = None,
    artifact_type: Optional[str] = None,
) -> Dict[str, Any]:
    from src.rag.query_engine import QueryEngine

    post_ids = None
    if group_name and user_id:
        group = load_group_by_name(user_id, group_name)
        if not group:
            raise ValueError(f"Group '{group_name}' not found for user.")
        if not user_can_access_group(user_id, group.id):
            raise ValueError(f"User does not have permission to access group '{group_name}'.")
        post_ids = get_post_ids_in_group(group.id)

    engine = QueryEngine()
    return engine.query(
        question=question,
        creator=creator,
        post_ids=post_ids,
        top_k=top_k,
        min_score=min_score,
        mode=mode,
        history=history,
        artifact_type=artifact_type,
    )


