import re

URL_SHORTCODE_RE = re.compile(r"/(?:p|reel|tv|stories)/([A-Za-z0-9_-]+)")


def shortcode_from_url(url: str) -> str:
    m = URL_SHORTCODE_RE.search(url)
    if not m:
        raise ValueError(f"Could not extract shortcode from URL: {url}")
    return m.group(1)
