# CLI Usage Guide

## Prerequisites
Ensure your `.env` file contains your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key
APIFY_API_KEY=your_apify_api_token
PINECONE_API_KEY=your_pinecone_api_key
```

## Commands

### 1. Profile Management
Add creators and specify tailored topics of interest:
```bash
# Add or update a profile
uv run python main.py profile add bejaranofit --interests "recetas, dieta, comida" --max-posts 50

# List all configured profiles and their progress
uv run python main.py profile list
```

### 2. Knowledge Ingestion Pipeline
Run the extraction pipeline on a profile:
```bash
uv run python main.py run bejaranofit
```
- Scrapes metadata from Instagram via Apify.
- Filters posts matching your defined interests.
- Downloads images, carousel slides, and videos.
- Extracts dense factual knowledge using Gemini multimodal vision & audio understanding.
- Indexes semantic vectors and full metadata into Pinecone.
- Saves a backup JSON locally in `data/processed/`.
- Deletes heavy media files immediately.

### 3. Saved Posts (Instagram data export)
Import your Instagram saved posts and index them ALL, without interest filtering:

```bash
# Import from a zip export (only saved_posts.json is extracted; all other
# personal data in the archive is discarded for privacy)
uv run python main.py saved import instagram-export.zip

# Or reference a plain saved_posts.json directly
uv run python main.py saved import your_instagram_activity/saved/saved_posts.json

# Show import/processing status
uv run python main.py saved status

# Process every pending saved post (parallel: 4 workers for download + analysis)
uv run python main.py saved process

# Control parallelism or process captions only (no media download)
uv run python main.py saved process --workers 8
uv run python main.py saved process --caption-only

# Process only the first N pending posts (useful for testing)
uv run python main.py saved process --limit 5

# Clear processed/failed history to re-process everything
uv run python main.py saved reset
```
- All saved posts are processed regardless of profile interests.
- Posts already indexed via any profile (or a previous saved run) are skipped automatically.
- Instagram's data export contains NO media for saved posts, so each post's media is fetched from its URL: yt-dlp first (video + audio merged via ffmpeg), then an authenticated instaloader session as fallback for reels that require login; if neither works, the caption is analyzed instead.
- To enable the instaloader fallback, create a session from your browser (Instagram blocks automated password logins with a generic 'fail' error, so use cookies instead):
  1. Log into instagram.com in **Firefox** (desktop site) and complete any security check. Chrome/Edge don't work: their cookies are encrypted with Windows app-bound encryption that cannot be read externally.
  2. **Close Firefox** (the cookie database must not be locked).
  3. `uv run python main.py auth-session YOUR_USERNAME --browser firefox`.
  4. `uv run python main.py config --ig-username YOUR_USERNAME`.
- Indexed under the `saved` collection: `uv run python main.py query "..." --creator saved`.

### 4. Querying the Knowledge Base (RAG)
Ask questions in natural language and receive grounded answers with direct links:
```bash
# Query across all creators
uv run python main.py query "¿Cómo preparar una pasta alta en proteínas?"

# Query filtered by a specific creator
uv run python main.py query "¿Qué ejercicios recomienda para espalda?" --creator bejaranofit
```
