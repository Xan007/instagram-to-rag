# Scraper Module (`src/scraper/`)

## Responsibility
Extracts post metadata (shortcode, direct URL, caption, hashtags, media types, and direct media URLs) for a given Instagram profile.

## Implementations

### 1. `ApifyScraper` (`src/scraper/apify_scraper.py`)
- **Primary engine** for reliable cloud scraping.
- Uses `apify-client` to trigger the `apify/instagram-scraper` Actor.
- Bypasses Instagram's aggressive 429 rate limiting, Checkpoints, and IP bans using managed proxy pools.
- Detects media types:
  - **Reels / Videos**: Extracts direct `.mp4` URLs.
  - **Single Images**: Extracts direct image URLs.
  - **Sidecars / Carousels**: Extracts all child slides (both images and video slides).
- Respects `skip_ids` by filtering out previously processed posts before yielding.

### 2. `LocalInstaloaderScraper` (`src/scraper/local_instaloader.py`)
- Secondary local fallback using `instaloader`.
- Supports session-based authenticated scraping to reduce blocks.
- Can be activated via `uv run python main.py config --scraper-engine instaloader`.
