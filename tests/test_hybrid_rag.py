import pytest
from src.rag.hybrid import HybridRetriever, tokenize
from src.rag.artifacts import get_artifact_system_prompt, ARTIFACT_PROMPTS
from storage.models import Post


def test_tokenize():
    text = "Press militar con mancuernas para hombro #fitness"
    tokens = tokenize(text)
    assert "press" in tokens
    assert "militar" in tokens
    assert "mancuernas" in tokens
    assert "fitness" in tokens


def test_hybrid_retriever_dense_and_sparse(tmp_path, monkeypatch):
    retriever = HybridRetriever(rrf_k=60)
    
    dense_matches = [
        {"id": "post1", "score": 0.85, "metadata": {"post_id": "post1", "url": "https://instagram.com/p/1", "extracted_knowledge": "Sentadillas profundas"}},
        {"id": "post2", "score": 0.70, "metadata": {"post_id": "post2", "url": "https://instagram.com/p/2", "extracted_knowledge": "Press banca plano"}},
    ]

    # Test combining without DB errors
    results = retriever.retrieve(
        query="press banca",
        pinecone_matches=dense_matches,
        top_k=2,
    )
    assert len(results) > 0
    assert any(r["metadata"]["post_id"] == "post2" for r in results)


def test_artifact_prompts():
    assert get_artifact_system_prompt("workout_plan") == ARTIFACT_PROMPTS["workout_plan"]
    assert get_artifact_system_prompt("recipe_book") == ARTIFACT_PROMPTS["recipe_book"]
    assert get_artifact_system_prompt("grocery_list") == ARTIFACT_PROMPTS["grocery_list"]
    assert get_artifact_system_prompt(None) is None
