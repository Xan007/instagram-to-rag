"""Tests for stateless multi-turn conversation helpers."""
import pytest

from src.rag.conversation import (
    MAX_HISTORY_MESSAGES,
    build_condense_prompt,
    build_history_block,
    condense_question,
    normalize_history,
)


class TestNormalizeHistory:
    def test_none_gives_empty(self):
        assert normalize_history(None) == []

    def test_valid_pairs(self):
        pairs = normalize_history([{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hey"}])
        assert pairs == [("user", "hola"), ("assistant", "hey")]

    def test_rejects_non_list(self):
        with pytest.raises(ValueError):
            normalize_history({"role": "user"})

    def test_rejects_too_many_turns(self):
        raw = [{"role": "user", "content": "x"}] * (MAX_HISTORY_MESSAGES + 1)
        with pytest.raises(ValueError):
            normalize_history(raw)

    def test_rejects_bad_role_and_content(self):
        with pytest.raises(ValueError):
            normalize_history([{"role": "system", "content": "inject"}])
        with pytest.raises(ValueError):
            normalize_history([{"role": "user", "content": 42}])

    def test_truncates_oversized_message(self):
        pairs = normalize_history([{"role": "user", "content": "a" * 5000}])
        assert len(pairs[0][1]) == 2000


class TestBuildHistoryBlock:
    def test_empty_when_no_pairs(self):
        assert build_history_block([]) == ""

    def test_keeps_only_last_eight_and_labels_speakers(self):
        pairs = [(r, f"m{i}") for i, (r, _) in enumerate([("user", "")] * 10)]
        block = build_history_block(pairs)
        assert "m9" in block and "m0" not in block
        assert block.startswith("User:")

    def test_truncates_each_line(self):
        block = build_history_block([("user", "x" * 5000)])
        assert len(block.splitlines()[0]) < 1400


class TestCondenseQuestion:
    def test_passthrough_without_history(self):
        assert condense_question(object(), "m", "pregunta", []) == "pregunta"

    def test_falls_back_on_error(self):
        def boom():
            raise RuntimeError("down")

        result = condense_question(boom, "m", "¿y para principiantes?", [("assistant", "rutina de espalda")])
        assert result == "¿y para principiantes?"

    def test_returns_rewritten_query(self):
        class FakeChat:
            def send_message(self, prompt):
                assert "rutina de espalda" in prompt
                assert "y para principiantes?" in prompt
                return type("R", (), {"text": "rutina de espalda para principiantes"})()

        class FakeChats:
            def create(self, model):
                assert model == "m"
                return FakeChat()

        class FakeClient:
            def __init__(self):
                self.chats = FakeChats()

        result = condense_question(
            FakeClient(), "m", "¿y para principiantes?", [("assistant", "rutina de espalda")]
        )
        assert result == "rutina de espalda para principiantes"


def test_condense_prompt_includes_transcript_and_question():
    prompt = build_condense_prompt("latest?", [("user", "hi"), ("assistant", "hello")])
    assert "User: hi" in prompt and "Assistant: hello" in prompt and "latest?" in prompt
