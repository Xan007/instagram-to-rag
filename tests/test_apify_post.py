"""Unit tests for the apify/instagram-scraper post normalization (offline)."""
from src.scraper.apify_post_scraper import _normalize_post, shortcode_from_url


def test_shortcode_from_url_reel_and_post():
    assert shortcode_from_url("https://www.instagram.com/reel/DcUfACpAXpQ/") == "DcUfACpAXpQ"
    assert shortcode_from_url("https://www.instagram.com/p/Db53Lx9gOz0/?img_index=1") == "Db53Lx9gOz0"


def test_normalize_video_post():
    item = {
        "type": "Video",
        "shortCode": "DcUfACpAXpQ",
        "caption": "Habilidades de calistenia #Calistenia",
        "url": "https://www.instagram.com/p/DcUfACpAXpQ/",
        "videoUrl": "https://cdn/video.mp4",
        "displayUrl": "https://cdn/thumb.jpg",
        "ownerUsername": "soynestorcordoba",
    }
    post = _normalize_post(item)
    assert post["id"] == "DcUfACpAXpQ"
    assert post["media_items"][0] == {"type": "video", "url": "https://cdn/video.mp4"}
    assert post["hashtags"] == ["Calistenia"]
    assert "calistenia" in post["description"].lower()


def test_normalize_sidecar_with_children():
    item = {
        "type": "Sidecar",
        "shortCode": "ABCsidecar1",
        "childPosts": [
            {"type": "Video", "videoUrl": "https://cdn/slide-video.mp4", "displayUrl": "https://cdn/sv.jpg"},
            {"type": "Image", "displayUrl": "https://cdn/slide-img.jpg"},
        ],
    }
    post = _normalize_post(item)
    types = [m["type"] for m in post["media_items"]]
    assert types == ["video", "image"]
    assert post["id"] == "ABCsidecar1"


def test_normalize_image_post_uses_images_list():
    item = {
        "shortCode": "ImgPost001",
        "images": ["https://cdn/a.jpg", "https://cdn/b.jpg"],
    }
    post = _normalize_post(item)
    assert len(post["media_items"]) == 2
    assert all(m["type"] == "image" for m in post["media_items"])


def test_normalize_falls_back_to_input_url_for_id():
    item = {"inputUrl": "https://www.instagram.com/reel/ZxYwVu98765/", "displayUrl": "https://cdn/x.jpg"}
    assert _normalize_post(item)["id"] == "ZxYwVu98765"


class TestShortcodeErrors:
    def test_invalid_url_raises(self):
        import pytest

        with pytest.raises(ValueError):
            shortcode_from_url("https://example.com/nope")
