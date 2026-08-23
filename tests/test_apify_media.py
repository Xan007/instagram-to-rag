"""Tests for sones/instagram-posts-scraper-lowcost output handling."""
import pytest

from src.scraper.apify_scraper import (
    _best_image_url,
    _best_video_url,
    _media_items_for,
    parse_newer_than,
    passes_newer_than,
)


class TestBestVideoUrl:
    def test_flat_field_wins(self):
        assert _best_video_url({"video_url": "https://cdn/flat.mp4", "video_versions": [{"url": "https://cdn/v.mp4"}]}) == "https://cdn/flat.mp4"

    def test_picks_highest_resolution_version(self):
        item = {"video_versions": [
            {"width": 480, "url": "https://cdn/low.mp4"},
            {"width": 720, "url": "https://cdn/mid.mp4"},
            {"width": 1080, "url": "https://cdn/high.mp4"},
        ]}
        assert _best_video_url(item) == "https://cdn/high.mp4"

    def test_none_when_missing(self):
        assert _best_video_url({}) is None


class TestBestImageUrl:
    def test_flat_field_wins(self):
        assert _best_image_url({"image_url": "https://cdn/flat.jpg", "image_versions2": {"candidates": [{"width": 1080, "url": "https://cdn/x.jpg"}]}}) == "https://cdn/flat.jpg"

    def test_prefers_candidate_within_1080(self):
        item = {"image_versions2": {"candidates": [
            {"width": 240, "url": "https://cdn/tiny.jpg"},
            {"width": 1080, "url": "https://cdn/std.jpg"},
            {"width": 1440, "url": "https://cdn/big.jpg"},
        ]}}
        assert _best_image_url(item) == "https://cdn/std.jpg"

    def test_falls_back_to_largest_when_all_oversized(self):
        item = {"image_versions2": {"candidates": [
            {"width": 2160, "url": "https://cdn/huge.jpg"},
            {"width": 1440, "url": "https://cdn/big.jpg"},
        ]}}
        assert _best_image_url(item) == "https://cdn/huge.jpg"


class TestMediaItems:
    def test_doc_format_without_flat_fields(self):
        item = {
            "media_type": 2,
            "video_versions": [{"width": 720, "url": "https://cdn/v.mp4"}],
            "image_versions2": {"candidates": [{"width": 1080, "url": "https://cdn/thumb.jpg"}]},
        }
        items = _media_items_for(item, 2)
        assert items == [{"type": "video", "url": "https://cdn/v.mp4"}]

    def test_carousel_mixed_children_with_nested_formats(self):
        item = {
            "media_type": 8,
            "carousel_media": [
                {"media_type": 2, "video_versions": [{"width": 640, "url": "https://cdn/sv.mp4"}]},
                {"media_type": 1, "image_versions2": {"candidates": [{"width": 1080, "url": "https://cdn/si.jpg"}]}},
            ],
        }
        items = _media_items_for(item, 8)
        assert [m["type"] for m in items] == ["video", "image"]


class TestNewerThanFiltering:
    def test_parse_formats(self):
        from datetime import datetime, timezone

        iso = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
        assert parse_newer_than("2026-01-01") == iso
        assert parse_newer_than("2026-01-01T00:00:00Z") == iso
        assert parse_newer_than(str(int(iso))) == iso
        assert parse_newer_than(str(int(iso * 1000))) == iso
        with pytest.raises(ValueError):
            parse_newer_than("gibberish-date")

    def test_actor_flag_is_trusted_first(self):
        cutoff = 1000.0
        assert passes_newer_than({"is_newer_than_cutoff": False, "taken_at": 5000}, cutoff) is False
        assert passes_newer_than({"is_newer_than_cutoff": True, "taken_at": 500}, cutoff) is True

    def test_taken_at_fallback_handles_seconds_and_ms(self):
        assert passes_newer_than({"taken_at": 1500}, 1000.0) is True
        assert passes_newer_than({"taken_at": 500}, 1000.0) is False
        assert passes_newer_than({"taken_at": 1_500_000}, 1000.0) is True
        assert passes_newer_than({}, 1000.0) is True

    def test_no_cutoff_passes_everything(self):
        assert passes_newer_than({"is_newer_than_cutoff": False}, None) is True
