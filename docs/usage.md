# CLI Usage Guide

## Prerequisites
Ensure your `.env` file contains your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key
APIFY_API_KEY=your_apify_api_token
PINECONE_API_KEY=your_pinecone_api_key
```

When using `instarag.exe`, each user must provide their own keys. Supported locations:
- `.env` next to `instarag.exe`
- `~/.instarag/.env` (recommended)
- OS environment variables

## Run as a global CLI (install once)

From the repository root:

```bash
uv tool install --from . instarag
uv tool update-shell
```

Restart your terminal and use:

```bash
instarag --help
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
- Instagram's data export contains NO media for saved posts, so each post's media is fetched from its URL with yt-dlp (video + audio merged via ffmpeg); if that fails, the caption is analyzed instead.
- Indexed under the `saved` collection: `uv run python main.py query "..." --creator saved`.

### Adding reels/posts by URL
```bash
# One or many URLs at once (uses apify/instagram-scraper; no login needed)
uv run python main.py add-reel https://www.instagram.com/reel/ABC/ https://www.instagram.com/p/DEF/

# Associate with a creator for duplicate tracking
uv run python main.py add-reel <url> --creator bejaranofit

# Analyze caption only (no media download)
uv run python main.py add-reel <url> --caption-only
```
- Metadata and direct media URLs come from the official `apify/instagram-scraper` Actor; videos are downloaded straight over HTTP.
- If Apify is unavailable, it falls back per URL to yt-dlp.
- Via API: `POST /jobs/add-reel {"urls": ["...", "..."]}`.

### 4. Querying the Knowledge Base (RAG)
Ask questions in natural language and receive grounded answers with direct links:
```bash
# Query across all creators (grounded_plus: creator content first; any general
# knowledge added is clearly labeled and never attributed to the creators)
uv run python main.py query "¿Cómo preparar una pasta alta en proteínas?"

# Query filtered by a specific creator
uv run python main.py query "¿Qué ejercicios recomienda para espalda?" --creator bejaranofit

# Absolute provenance: refuse instead of supplementing with general knowledge
uv run python main.py query "..." --mode strict

# Tune retrieval: more candidates, stricter trust threshold
uv run python main.py query "..." --top-k 12 --min-score 0.5

# Follow-up using a prior conversation (stateless: the file is client-side)
uv run python main.py query "¿y para principiantes?" --history turns.json

# Interactive multi-turn chat (history kept in-process, sent every turn)
uv run python main.py chat --creator bejaranofit
```
- Matches below `--min-score` are discarded; if nothing is relevant enough you get an honest "no encontré contenido" answer plus the closest indexed links.
- The original post caption is included in the context alongside the extracted knowledge.
