import pytest
from src.agent.intent import ArtifactIntentDetector, ArtifactIntent
from src.agent.delegator import AgentArtifactDelegator


def test_artifact_intent_detector_workout():
    intent = ArtifactIntentDetector.detect("Arma una rutina de torso y pierna de 4 dias en pdf")
    assert intent.should_generate is True
    assert intent.artifact_type == "workout_plan"
    assert intent.output_format == "pdf"


def test_artifact_intent_detector_grocery():
    intent = ArtifactIntentDetector.detect("Dame la lista de compras del mercado en markdown")
    assert intent.should_generate is True
    assert intent.artifact_type == "grocery_list"
    assert intent.output_format == "md"


def test_artifact_intent_detector_pure_question():
    intent = ArtifactIntentDetector.detect("Quien es bejaranofit?")
    assert intent.should_generate is False


def test_agent_artifact_delegator(tmp_path):
    intent = ArtifactIntent(
        should_generate=True,
        artifact_type="workout_plan",
        output_format="pdf",
        suggested_filename=str(tmp_path / "test_delegated.pdf"),
        title="Rutina Delegada",
    )
    answer = "### Dia 1: Torso\n\n| Ejercicio | Series | Reps | Notas |\n|---|---|---|---|\n| Press | 4 | 8 | Fuerza [Source 1] |"
    sources = [{"creator": "coach", "url": "https://instagram.com/p/1", "cited": True, "summary": "Press"}]

    res = AgentArtifactDelegator.process_and_export(
        answer=answer,
        sources=sources,
        intent=intent,
    )
    assert res is not None
    assert "test_delegated.pdf" in res["filename"]
