# Scraper Module (`src/scraper/`)

## Responsibility
Extracts post metadata (shortcode, direct URL, caption, hashtags, media types, and direct media URLs) for a given Instagram profile.

## Implementations

### 1. `ApifyScraper` (`src/scraper/apify_scraper.py`)
- **Primary engine** for reliable cloud scraping.
- Uses `apify-client` to trigger the `sones/instagram-posts-scraper-lowcost` Actor (`postsPerProfile` capped at 500).
- Handles BOTH output formats of the Actor: flat fields (`video_url`, `image_url`) and native Instagram structures (`video_versions[]`, `image_versions2.candidates[]`), always picking the highest-quality source (images ~1080px).
- `newerThan` is only a pagination boundary for the Actor, so results are **re-filtered locally** via `is_newer_than_cutoff` / `taken_at` to guarantee no post older than the cutoff is yielded.
- On empty runs, logs the actor's `RUN_SUMMARY` record (from its key-value store) for diagnostics.
- Detects media types:
  - **Reels / Videos**: extracts direct video URLs.
  - **Single Images**: extracts direct image URLs.
  - **Sidecars / Carousels**: extracts all child slides (both images and video slides).
- Respects `skip_ids` by filtering out previously processed posts before yielding.

### 2. `ApifyPostScraper` (`src/scraper/apify_post_scraper.py`)
- **Used ONLY by the add-reel flow** (single/multiple URLs).
- Calls the official `apify/instagram-scraper` Actor with `resultsType: "posts"` + `directUrls`.
- Returns normalized post dicts with **direct media URLs** (`videoUrl`, images, sidecar children); videos are downloaded straight over HTTP — no login and no yt-dlp needed for ingestion.
- Per-URL fallback when Apify is unavailable: yt-dlp (metadata + download).

> **No instaloader**: session-based scraping was removed entirely. All media
> comes from actor responses or yt-dlp; no cookies or Instagram sessions are used.
