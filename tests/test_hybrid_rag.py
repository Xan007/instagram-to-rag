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


def test_export_artifact_md_and_pdf(tmp_path):
    from src.rag.artifacts import export_artifact

    md_file = tmp_path / "plan.md"
    pdf_file = tmp_path / "plan.pdf"
    content = "# Rutina de Empuje\n\n- Press militar: 4x8 [Source 1]\n- Elevaciones laterales: 3x12 [Source 1]"
    sources = [{"creator": "coach", "url": "https://instagram.com/p/abc", "cited": True}]

    res_md = export_artifact(content, str(md_file), title="Rutina", sources=sources)
    assert res_md.exists()
    assert "Press militar" in res_md.read_text(encoding="utf-8")

    res_pdf = export_artifact(content, str(pdf_file), title="Rutina", sources=sources)
    assert res_pdf.exists()
    assert res_pdf.stat().st_size > 500


def test_export_artifact_table_pdf(tmp_path):
    from src.rag.artifacts import export_artifact

    pdf_file = tmp_path / "workout_table.pdf"
    table_content = """# Plan Semanal de Entrenamiento

A continuación la división completa de la semana:

| Día | Ejercicio | Series | Repeticiones | Notas |
|---|---|---|---|---|
| Lunes | Press Militar | 4 | 8-10 | Codos a 45° [Source 1] |
| Miércoles | Peso Muerto Rumano | 3 | 10-12 | Espalda recta [Source 2] |
| Viernes | Dominadas Pronas | 4 | Al fallo | Rango completo [Source 1] |

> Recuerda calentar 5 minutos antes de comenzar cada sesión.
"""
    sources = [
        {"creator": "fitness_pro", "url": "https://instagram.com/p/123", "cited": True},
        {"creator": "nutrition_coach", "url": "https://instagram.com/p/456", "cited": True},
    ]

    res_pdf = export_artifact(table_content, str(pdf_file), title="Rutina Premium con Tabla", sources=sources)
    assert res_pdf.exists()
    assert res_pdf.stat().st_size > 1500


def test_export_artifact_multi_source_brackets(tmp_path):
    from src.rag.artifacts import export_artifact, _md_to_reportlab_html

    converted = _md_to_reportlab_html("Basado en [Source 1, Source 2, Source 5].")
    assert 'href="#source_1"' in converted
    assert 'href="#source_2"' in converted
    assert 'href="#source_5"' in converted

    pdf_file = tmp_path / "multi_source.pdf"
    content = "Consejos combinados [Source 1, Source 2]."
    sources = [
        {"creator": "a", "url": "https://instagram.com/p/a", "cited": True},
        {"creator": "b", "url": "https://instagram.com/p/b", "cited": True},
    ]
    res_pdf = export_artifact(content, str(pdf_file), title="Multi Source", sources=sources)
    assert res_pdf.exists()



