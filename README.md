<div align="center">

# InstaRAG

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pinecone](https://img.shields.io/badge/Pinecone-000000?logo=pinecone&logoColor=white)](https://www.pinecone.io/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

InstaRAG is a modular, production-ready Instagram knowledge extraction and Retrieval-Augmented Generation (RAG) system. It ingests public creator profiles, standalone reels, and saved post archives, extracts multimodal knowledge using Google Gemini and Faster-Whisper, indexes semantic representations into Pinecone, and delivers grounded answers, multi-turn conversational agents, and structured document exports (PDF/Markdown).

---

## Features

- **Multimodal Video & Audio Extraction:** Transcribes speech, extracts on-screen text overlays, and captures structured facts (measurements, ingredients, exercise forms, and technical steps) using Google Gemini and Faster-Whisper.
- **Hybrid Retrieval (Dense + BM25):** Combines dense vector similarity with BM25 sparse keyword ranking via Reciprocal Rank Fusion (RRF) for optimal precision and recall.
- **Modular Multi-Provider Embeddings:** Pluggable embedding providers supporting Jina AI v3, Google Gemini (`text-embedding-004`), and 100% local ONNX FastEmbed (`BAAI/bge-small-en-v1.5`) with automatic fallback failover.
- **Autonomous Agentic Delegation:** Automatically detects user intent to produce structured artifacts (`workout_plan`, `recipe_book`, `grocery_list`) and exports them to styled PDF or Markdown documents.
- **Executive PDF Rendering Engine:** Generates clean, minimalist documents with structured tables, direct clickable links to Instagram reels, and concise source summaries.
- **Multi-Tenant Scoped Groups:** Define isolated knowledge domains (e.g. Fitness, Cooking, Biohacking) and grant shared read permissions across accounts.
- **Deduplicated Knowledge Base:** Shared creator posts are ingested and embedded only once globally across all users and groups.
- **Production REST API:** High-performance FastAPI server with asynchronous background job workers, live log streaming, and healthcheck endpoints.

---

## Architecture

```mermaid
flowchart TD
    IG[Instagram Content: Profiles, Reels, Saved Archives] --> Downloader[Media Downloader: yt-dlp & FFmpeg]
    Downloader --> Analyzer[Multimodal Analyzer: Gemini / Faster-Whisper]
    Analyzer --> DB[(SQL Database: SQLite / PostgreSQL)]
    Analyzer --> Embedder[Modular Embedder: Jina / Gemini / FastEmbed]
    Embedder --> VectorDB[(Pinecone Vector DB)]
    
    UserQuery[User Question / Chat Session] --> Detector[Agent Intent Detector]
    Detector --> Retriever[Hybrid Retriever: Pinecone + Local BM25]
    Retriever --> LLM[Gemini / Groq / OpenAI Compatible LLM]
    LLM --> Delegator[Agent Artifact Delegator]
    Delegator --> Output[Interactive Response + Styled PDF / Markdown]
```

---

## Installation

### Prerequisites
- Python 3.12+ (Python 3.14 compatible)
- FFmpeg installed on system path
- `uv` package manager (or `pip`)

### 1. Clone and Install Dependencies
```bash
git clone https://github.com/your-username/instarag.git
cd instarag
uv sync --extra api
```

### 2. Environment Configuration
Create a `.env` file in the project root:
```ini
# Required API Keys
GEMINI_API_KEY=your_gemini_api_key
PINECONE_API_KEY=your_pinecone_api_key
APIFY_API_KEY=your_apify_api_key

# LLM Providers (Optional / Fallback)
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_api_key
JINA_API_KEY=your_jina_api_key

# Model & Provider Configuration
EMBED_PROVIDER=auto              # auto | jina | gemini | fastembed
FILTER_PROVIDER=gemini           # gemini | openai | groq
FILTER_MODEL=gemini-2.5-flash
RAG_PROVIDER=gemini              # gemini | openai | groq
RAG_MODEL=gemini-2.5-flash

# Database & Server Settings
INSTARAG_DATABASE_URL=sqlite:////data/instarag.db  # or postgresql+psycopg://...
PORT=8000
INSTARAG_PORT=8000
INSTARAG_HOST=0.0.0.0
INSTARAG_API_KEY=your_optional_secret_api_key
INSTARAG_CORS_ORIGINS=http://localhost:3000
INSTARAG_USER=default_user
INSTARAG_AUTO_CREATE_USERS=true
```

---

## Command Line Interface (CLI)

> [!TIP]
> Once installed globally with `uv tool install --editable .`, you can use `instarag` directly. Alternatively, use `uv run instarag <command>`.

### User Management
```bash
# Create a local user account
instarag user create <username>

# List registered accounts
instarag user list
```

### Profile Management & Scraping
```bash
# Register a creator profile (optionally with default interests filter)
instarag profile add <creator_username> --interests "calisthenics, mobility"

# Scrape posts: indexes metadata, downloading media for matching interests
instarag profile scrape <creator_username> --max-posts 50 --interests "calisthenics, mobility"

# Incremental update since last scrape date
instarag profile update <creator_username>

# List tracked creator profiles
instarag profile list
```

### Scoped RAG Groups (Agents)
```bash
# Create a scoped group / knowledge agent
instarag group create <group_name> --desc "Topic Knowledge Base"

# List groups accessible to the user
instarag group list

# Add posts from a creator profile (with optional topic filtering)
instarag group add-from-profile <group_name> <creator_username> --interests "workout, hypertrophy"

# Add a single reel or post URL / shortcode ID to a group
instarag group add-post <group_name> https://instagram.com/reel/<shortcode>/

# Share group access with another user
instarag group share <group_name> <target_username>
```

### Saved Posts Ingestion
```bash
# Import saved posts archive (.zip export or saved_posts.json)
instarag saved import <path_to_saved_posts.json>

# Process and index imported saved posts with background workers
instarag saved process --workers 4
```

### Knowledge Query & Document Export
```bash
# General query with hybrid search
instarag query "Explain the proper technique for shoulder press"

# Query scoped to a group with autonomous PDF export
instarag query "Create a 4-day upper lower workout routine in PDF" -g <group_name> -o routine.pdf

# Query scoped to a specific creator with Markdown export
instarag query "Consolidate the ingredients for weekly meal prep" -c <creator_username> -o grocery_list.md

# Specify RAG mode ('grounded_plus' or 'strict')
instarag query "What supplements are recommended?" --mode strict --top-k 8
```

### Interactive Multi-Turn Chat
```bash
# Start an interactive conversational session scoped to a group or creator
instarag chat -g <group_name>
instarag chat -c <creator_username>
```

---

## HTTP REST API

Start the API server:
```bash
instarag-api
# or via uv:
# uv run python -m src.api.main
```
Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### Core Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health and liveness status |
| `GET` / `PATCH` | `/config` | Inspect or update global settings (`audio_only`, `engine`, `embed_provider`) |
| `GET` / `POST` | `/users` | List registered local users or create a new user |
| `GET` / `DELETE` | `/users/{username}` | Retrieve user information or delete a user account |
| `GET` / `POST` | `/groups` | List user groups or create a new scoped RAG group |
| `GET` / `DELETE` | `/groups/{group_id}` | Inspect group details and post IDs or delete a group |
| `POST` / `DELETE` | `/groups/{group_id}/posts` | Add/remove posts, reels, or profile contents to a group |
| `POST` / `DELETE` | `/groups/{group_id}/share` | Share or unshare group access with another user |
| `GET` / `POST` | `/profiles` | List registered creator profiles or register a new profile |
| `GET` / `PATCH` / `DELETE` | `/profiles/{username}` | Retrieve, update, or remove a creator profile |
| `POST` | `/profiles/{username}/reset` | Reset processing history for a creator profile |
| `POST` | `/jobs/run` | Trigger asynchronous profile ingestion background job |
| `POST` | `/jobs/add-reel` | Ingest standalone reel URLs asynchronously |
| `POST` | `/jobs/saved-process` | Trigger asynchronous saved posts indexing worker |
| `GET` | `/jobs` | List recent background jobs and worker queue state |
| `GET` | `/jobs/{job_id}` | Monitor background task progress and inspect logs |
| `POST` | `/saved/import` | Upload an Instagram export archive (`.zip` or `.json`) |
| `GET` | `/saved/status` | Retrieve import statistics and pending count |
| `POST` | `/saved/reset` | Clear processed saved posts state |
| `POST` | `/query` | Execute grounded RAG query with multi-turn history & artifact delegation |

---

## Docker & Cloud Deployment

### Build and Run Locally
```bash
docker build -t instarag:latest .
docker run -d -p 8000:8000 -v instarag_data:/data --env-file .env instarag:latest
```

### Or using Docker Compose:
```bash
docker compose up -d --build
```

### Cloud Platforms (Render, Railway, Fly.io, Google Cloud Run)
- Executes securely as a non-root user (`instarag`).
- Dynamically binds to the environment `$PORT` (default `8000`).
- Persistent data stored under `/data` (mount volume for SQLite/local caches).
- Automated container healthcheck on `/health`.

---

## Testing

Run the test suite:
```bash
uv run pytest
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
