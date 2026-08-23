<div align="center">

# InstaRAG

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-embedding%20%2B%20analysis-4285F4?logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-HTTP%20API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

</div>

InstaRAG turns Instagram content into a queryable knowledge base. It scrapes profiles and saved posts through Apify actors, extracts dense knowledge from videos and images with Gemini multimodal analysis, indexes everything into a Pinecone vector database, and serves grounded RAG answers through both a CLI and an HTTP API designed for UI consumption.

No Instagram sessions or cookies are used anywhere: media comes from actor-provided CDN URLs or yt-dlp.

## Features

- **Profile pipelines** — scrape → interest filter (batched LLM call) → download → analyze → index, with per-profile dedup and resume.
- **Saved posts** — import your Instagram data export (`zip` or `saved_posts.json`) and process every saved post without interest filtering.
- **Reels by URL** — ingest one or many posts/reels in a single call via the official `apify/instagram-scraper` actor; videos download straight over HTTP.
- **Structured knowledge extraction** — fixed markdown sections, literal numbers (sets×reps, grams, seconds), on-screen text and spoken key points preserved.
- **Grounded RAG answers** — citations with `[Source N]`, `cited` flag per source, dual answer mode (`grounded_plus` default / `strict`), similarity threshold, tunable retrieval.
- **Multi-turn conversations** — stateless history contract; follow-ups like "¿y para principiantes?" are condensed into standalone search queries before retrieval.
- **HTTP API** — FastAPI with background jobs (serialized worker, live logs echoed to console) and auto-generated OpenAPI docs at `/docs`.

## Tech Stack

- Python 3.14 + uv
- Google Gemini — multimodal extraction, embeddings (`gemini-embedding-001`), answer generation
- Pinecone serverless — vector database
- Apify actors — `sones/instagram-posts-scraper-lowcost` (profiles), `apify/instagram-scraper` (URLs)
- FastAPI + Uvicorn (HTTP API) · Typer + Rich (CLI)
- yt-dlp (fallback downloads) · faster-whisper / OpenAI Whisper (optional audio transcription)

## Installation

```bash
uv sync                # CLI only
uv sync --extra api    # CLI + HTTP API
```

### Install once, use from any folder (Windows CMD/PowerShell)

```bash
uv tool install --from . instarag
uv tool update-shell
```

Then open a new terminal and run:

```bash
instarag --help
```

### Build a Windows `.exe`

```bash
uv tool run pyinstaller --onefile --name instarag main.py
```

Binary output:
- `dist/instarag.exe`

## Configuration

Create a `.env` file with your own keys:

```env
GEMINI_API_KEY=your_key
PINECONE_API_KEY=your_key
APIFY_API_KEY=your_apify_token
```

Optional API settings:

| Variable | Purpose |
| --- | --- |
| `INSTARAG_API_KEY` | Require an `X-API-Key` header on every endpoint |
| `INSTARAG_CORS_ORIGINS` | Comma-separated browser origins allowed to call the API |
| `INSTARAG_DATA_DIR` | Media/state root (default `./data`) |
| `INSTARAG_CONFIG_DIR` | Settings/profiles root (default `~/.instarag`) |
| `INSTARAG_HOST` / `INSTARAG_PORT` | API bind address |

For the `.exe`, each user should configure their own keys in one of these locations:
- `.\.env` (same folder where `instarag.exe` is located)
- `~/.instarag/.env` (recommended for persistent per-user setup)
- System environment variables

## Usage

```bash
# Add a profile and process it
instarag profile add <username> --interests "recetas, dieta" --max-posts 50
instarag run <username>

# Ingest one or many reels/posts by URL (no login needed)
instarag add-reel https://www.instagram.com/reel/ABC/ https://www.instagram.com/p/DEF/

# Process saved posts from an Instagram data export
instarag saved import export.zip
instarag saved process

# Ask questions (grounded_plus by default)
instarag query "your question here" --creator <your_target>
instarag query "..." --mode strict --top-k 12

# Interactive multi-turn chat
instarag chat --creator <your_target>
```

## HTTP API

```bash
uv run api.py            # http://127.0.0.1:8000 — OpenAPI docs at /docs
```

```bash
curl -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" -d '{
  "question": "¿y para principiantes?",
  "history": [
    {"role": "user", "content": "rutina de calistenia de espalda"},
    {"role": "assistant", "content": "dominadas, remos australianos..."}
  ]
}'
```

Heavy operations (`run`, `add-reel`, `saved-process`) return `202` with a `job_id`; poll `GET /jobs/{id}` for status and live logs.

### Docker (any host)

```bash
docker build -t instarag-api .
docker run -p 8000:8000 -v instarag-data:/data \
  -e GEMINI_API_KEY=... -e PINECONE_API_KEY=... -e APIFY_API_KEY=... \
  instarag-api
```

See [docs/api.md](docs/api.md) for the full endpoint table and an Azure Container Apps example.

## Commands

| Command | Description |
| --- | --- |
| `profile` | Manage Instagram profiles |
| `run` | Extract and index knowledge from a profile |
| `saved` | Import and process saved posts |
| `add-reel` | Add one or more reels/posts by URL |
| `query` | Ask the knowledge base (supports `--history` for follow-ups) |
| `chat` | Interactive multi-turn conversation |
| `config` | Configure global settings |

## Testing

```bash
uv sync --extra api   # once (installs API deps + pytest)
uv run pytest         # unit + HTTP API tests (no network, isolated temp state)
```

## Documentation

- [Usage guide](docs/usage.md)
- [HTTP API](docs/api.md)
- [Architecture](docs/architecture.md)
- [Indexer and RAG](docs/modules/indexer_and_rag.md)
