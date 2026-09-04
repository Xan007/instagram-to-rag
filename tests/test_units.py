"""Pure unit tests for config parsing and state models (no network, no API keys)."""
import json

from config.profiles import ProfileConfig, delete_profile, load_profile, save_profile
from config.saved import SavedState, load_state, parse_saved_posts, save_state
from config.settings import AppSettings


def _label_item(url: str) -> dict:
    return {
        "label_values": [
            {"label": "URL", "value": url},
            {"label": "Pie de foto", "value": "caption text"},
            {"label": "Título", "value": "a title"},
        ]
    }


class TestParseSavedPosts:
    def test_label_values_spanish_export(self):
        items = parse_saved_posts([_label_item("https://www.instagram.com/reel/ABC123_/")])
        assert len(items) == 1
        post = items[0]
        assert post["id"] == "ABC123_"
        assert post["caption"] == "caption text"
        assert post["title"] == "a title"

    def test_plain_format(self):
        items = parse_saved_posts(
            [{"url": "https://www.instagram.com/p/xyz123/", "caption": "cap", "title": "t"}]
        )
        assert items[0]["id"] == "xyz123"

    def test_dict_wrapper(self):
        data = {"saved_posts": [_label_item("https://www.instagram.com/p/abc/")]}
        assert len(parse_saved_posts(data)) == 1

    def test_unsupported_shape_raises(self):
        import pytest

        with pytest.raises(ValueError):
            parse_saved_posts("not-a-list")

    def test_items_without_url_are_skipped(self):
        assert parse_saved_posts([{"caption": "no url here"}, "junk", 42]) == []


class TestSavedState:
    def test_roundtrip(self):
        state = SavedState(total=3, processed_ids=["a"], failed_ids=["b"])
        save_state(state)
        loaded = load_state()
        assert loaded.total == 3
        assert loaded.processed_ids == ["a"]
        assert loaded.failed_ids == ["b"]

    def test_to_dict_is_a_copy(self):
        state = SavedState()
        d = state.to_dict()
        d["processed_ids"].append("x")
        assert state.processed_ids == []

    def test_fresh_lists_per_instance(self):
        s1, s2 = SavedState(), SavedState()
        s1.processed_ids.append("only-s1")
        assert s2.processed_ids == []


class TestProfileConfig:
    def test_roundtrip(self):
        profile = ProfileConfig(username="_unit", interests="comida", max_posts=7)
        profile.processed_ids.append("post1")
        profile.failed_ids.append("post2")
        save_profile(profile)

        loaded = load_profile("_unit")
        assert loaded.interests == "comida"
        assert loaded.max_posts == 7
        assert loaded.processed_ids == ["post1"]
        assert loaded.failed_ids == ["post2"]
        delete_profile("_unit")
        assert load_profile("_unit") is None


class TestIGProfileInfo:
    def test_ig_profile_interests_roundtrip(self):
        from config.ig_profiles import IGProfileInfo, delete_ig_profile, load_ig_profile, save_ig_profile
        p = IGProfileInfo(username="_ig_unit_test", interests="calisthenics, mobility")
        save_ig_profile(p)

        loaded = load_ig_profile("_ig_unit_test")
        assert loaded is not None
        assert loaded.username == "_ig_unit_test"
        assert loaded.interests == "calisthenics, mobility"

        delete_ig_profile("_ig_unit_test")
        assert load_ig_profile("_ig_unit_test") is None


class TestAppSettings:
    def test_from_dict_ignores_unknown_keys(self):
        settings = AppSettings.from_dict({"engine": "local_whisper", "future_field": 1, "ig_username": "legacy"})
        assert settings.engine == "local_whisper"
        assert not hasattr(settings, "future_field")
        assert not hasattr(settings, "ig_username")

    def test_settings_roundtrip(self):
        from config.settings import load_settings, save_settings

        original = load_settings()
        try:
            save_settings(AppSettings(engine="local_whisper", embed_provider="local", audio_only=True))
            loaded = load_settings()
            assert loaded.engine == "local_whisper"
            assert loaded.embed_provider == "local"
            assert loaded.audio_only is True
        finally:
            save_settings(original)
