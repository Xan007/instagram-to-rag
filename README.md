<div align="center">

# InstaRAG

[![Python](https://img.shields.io/badge/Python-3.12%20|%203.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-embedding%20%2B%20analysis-4285F4?logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![Pinecone](https://img.shields.io/badge/Pinecone-vector%20DB-000000?logo=pinecone&logoColor=white)](https://www.pinecone.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-HTTP%20API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

</div>

InstaRAG is a modular, multi-tenant Instagram knowledge extraction pipeline and Retrieval-Augmented Generation (RAG) platform. It ingests public Instagram creator profiles, individual reels, and user data exports, transcribes audio and analyzes video visuals via Google Gemini multimodal models, indexes deduplicated semantic vectors into Pinecone, and enables users to create, query, and share custom topic-scoped RAG agents (Groups).

---

## Table of Contents

- [Core Capabilities](#core-capabilities)
- [System Architecture](#system-architecture)
- [Prerequisites](#prerequisites)
- [Installation Guide](#installation-guide)
  - [Option 1: Local Environment with uv](#option-1-local-environment-with-uv)
  - [Option 2: Global CLI Tool Installation](#option-2-global-cli-tool-installation)
  - [Option 3: Docker and Docker Compose](#option-3-docker-and-docker-compose)
  - [Option 4: Standalone Windows Binary (.exe)](#option-4-standalone-windows-binary-exe)
- [Configuration and Environment Variables](#configuration-and-environment-variables)
- [CLI Quickstart Guide](#cli-quickstart-guide)
  - [1. User Management](#1-user-management)
  - [2. Global Creator Ingestion](#2-global-creator-ingestion)
  - [3. Scoped RAG Agents and Groups](#3-scoped-rag-agents-and-groups)
  - [4. Saved Posts Ingestion](#4-saved-posts-ingestion)
  - [5. Standalone Reel Ingestion](#5-standalone-reel-ingestion)
  - [6. Querying and Multi-Turn Chat](#6-querying-and-multi-turn-chat)
- [HTTP REST API](#http-rest-api)
- [Database Support](#database-support)
- [Testing](#testing)
- [Documentation Index](#documentation-index)

---

## Core Capabilities

- **Multi-Account and Scoped RAG Agents (Groups):** Users can define isolated RAG agents (such as Nutrition, Fitness, Cooking Recipes, or Biohacking), populate them with relevant reels either manually or by applying LLM interest filters, and share read access with other users.
- **Global Knowledge Deduplication:** Creator posts and reels are ingested and analyzed once globally. If multiple users track the same creator or bookmark the same reel, knowledge extraction and Pinecone vector upsert are never duplicated.
- **Identity and Database Agnostic:** Powered by SQLAlchemy 2.0. Switch between SQLite, PostgreSQL, Supabase, or Neon simply by changing the `INSTARAG_DATABASE_URL` environment variable. User identifiers are stored as generic strings, making authentication pluggable (Clerk, Supabase Auth, Firebase, JWTs).
- **Multimodal Video Understanding:** Extracts dense factual knowledge including numerical metrics (reps, sets, grams, cooking temperatures, minutes), on-screen text overlays, and spoken voice transcripts.
- **Dual Response Modes and Exact Provenance:** Includes verifiable Instagram source citations (`[Source N]`) with direct URLs. Offers `grounded_plus` mode (creator knowledge first with clearly labeled general fallback) and `strict` mode (absolute provenance only).
- **Stateless Conversation Continuity:** Multi-turn chat questions (for instance: "what about beginners?") are dynamically condensed into standalone retrieval queries before vector search.

---

## System Architecture

```mermaid
flowchart TD
    subgraph Multi-Tenant Identity
        U[Users] -->|Owns| G[Groups / RAG Agents]
        G -->|Shared with| S[GroupShare Permissions]
        S -->|Access granted to| U
    end

    subgraph Global Ingestion Engine
        IG[Global IG Profiles] --> Scraper[Apify Scraper]
        ReelURL[Reel URLs] --> ScraperURL[Apify Post Scraper / yt-dlp]
        SavedExport[User Saved Posts Export] --> SavedParser[Saved Posts Parser]
        
        Scraper --> Downloader[Media Downloader / yt-dlp]
        ScraperURL --> Downloader
        SavedParser --> Downloader
        
        Downloader --> Analyzer[Gemini Multimodal Analyzer / Whisper]
        Analyzer --> PostDB[(Relational DB: SQLite / Postgres / Supabase)]
        Analyzer --> Indexer[Pinecone Vector Indexer]
        Indexer --> Pinecone[(Pinecone Vector DB)]
    end

    subgraph Retrieval & Generation
        G --> GP[Group Posts Association]
        GP -->|Filters by post_id list| QueryEngine[RAG Query Engine]
        QueryEngine -->|Vector Search with Metadata Filter| Pinecone
        Pinecone -->|Relevant Knowledge Chunks| Generator[Gemini Response Generator]
        Generator --> Answer[Answer with Source Citations]
    end
```

---

## Prerequisites

- **Python:** Version 3.12 or 3.14 recommended.
- **Package Manager:** `uv` (recommended) or standard `pip`.
- **System Tools:** `ffmpeg` (required for audio extraction and video downloads).
- **API Keys:**
  - [Google Gemini API Key](https://ai.google.dev/) (used for embeddings, vision, audio analysis, and response generation).
  - [Pinecone API Key](https://www.pinecone.io/) (used for vector storage and retrieval).
  - [Apify API Key](https://apify.com/) (used for Instagram scraping actors).

---

## Installation Guide

### Option 1: Local Environment with uv

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/ig-profile-to-rag.git
   cd ig-profile-to-rag
   ```

2. Install `uv` if not already installed:
   ```bash
   # On macOS/Linux:
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # On Windows (PowerShell):
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. Install project dependencies:
   ```bash
   # Install CLI dependencies:
   uv sync

   # Install CLI and FastAPI HTTP API dependencies:
   uv sync --extra api
   ```

4. Verify installation:
   ```bash
   uv run python main.py --help
   ```

---

### Option 2: Global CLI Tool Installation

You can install InstaRAG globally on your machine so you can run `instarag` from any directory:

```bash
uv tool install --from . instarag
uv tool update-shell
```

Restart your terminal and run:
```bash
instarag --help
```

---

### Option 3: Docker and Docker Compose

1. Copy the environment configuration:
   ```bash
   cp .env.example .env
   ```
2. Populate `.env` with your API keys.
3. Build and launch the container:
   ```bash
   docker compose up -d --build
   ```
4. Access the API documentation at `http://localhost:8000/docs`.

---

### Option 4: Standalone Windows Binary (.exe)

You can compile a standalone executable file:

```bash
uv tool run pyinstaller --onefile --name instarag main.py
```

The resulting binary will be created at `dist/instarag.exe`. Users can place a `.env` file in the same folder or in `~/.instarag/.env`.

---

## Configuration and Environment Variables

Create a `.env` file in the root directory:

```env
# Required Provider API Keys
GEMINI_API_KEY=your_gemini_api_key
PINECONE_API_KEY=your_pinecone_api_key
APIFY_API_KEY=your_apify_api_key

# Database Connection (Optional - defaults to SQLite at ~/.instarag/instarag.db)
# For Supabase / PostgreSQL / Neon:
# INSTARAG_DATABASE_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres

# Server & Networking
PORT=8000
INSTARAG_HOST=0.0.0.0
INSTARAG_PORT=8000

# Optional API Security
# INSTARAG_API_KEY=your_secret_api_key
# INSTARAG_CORS_ORIGINS=http://localhost:3000,https://app.example.com
```

---

## CLI Quickstart Guide

### 1. User Management
Create and manage local accounts:
```bash
# Create user accounts
python main.py user create john
python main.py user create alice

# List all accounts
python main.py user list
```

### 2. Global Creator Ingestion
Scrape and extract knowledge from Instagram creators globally (deduplicated across users):
```bash
# Register a creator
python main.py profile add fitness_coach

# Ingest and index all creator posts into the database and Pinecone
python main.py profile scrape fitness_coach --max-posts 100

# Perform an incremental scrape (only fetch posts published after the last run)
python main.py profile update fitness_coach

# List all registered profiles
python main.py profile list
```

### 3. Scoped RAG Agents and Groups
Create dedicated topic-based knowledge agents, populate them with posts, and share access:
```bash
# Create a new RAG Agent group
python main.py group create HealthyRecipes --user john --desc "High protein recipes and kitchen tips"

# Populate the agent from a creator profile, applying an interest filter
python main.py group add-from-profile HealthyRecipes fitness_coach --interests "recipes, breakfast, high protein" --user john

# Add a specific post or reel directly by URL
python main.py group add-post HealthyRecipes "https://www.instagram.com/reel/C8xyz123/" --user john

# Share the agent with another user
python main.py group share HealthyRecipes alice --user john

# List available groups (shows owned and shared agents)
python main.py group list --user alice
```

### 4. Saved Posts Ingestion
Import and extract knowledge from your Instagram saved posts export:
```bash
# Import your Instagram data export (ZIP archive or saved_posts.json)
python main.py saved import export.zip --user john

# Process and index imported saved posts
python main.py saved process --user john --workers 4
```

### 5. Standalone Reel Ingestion
Ingest arbitrary Instagram reels or posts without registering a creator profile:
```bash
python main.py add-reel https://www.instagram.com/reel/ABC123/ https://www.instagram.com/p/DEF456/
```

### 6. Querying and Multi-Turn Chat
Query the entire knowledge base or restrict questions to a specific RAG Agent:
```bash
# Query a specific RAG Agent
python main.py query "What are three quick breakfast ideas?" --group HealthyRecipes --user john

# Query with strict creator-only provenance
python main.py query "What exercises are recommended for lower back?" --creator fitness_coach --mode strict

# Interactive multi-turn conversational chat
python main.py chat --group HealthyRecipes --user alice
```

---

## HTTP REST API

Run the FastAPI service locally:
```bash
uv run python -m src.api.main
```
Interactive OpenAPI documentation will be served at `http://127.0.0.1:8000/docs`.

### Key Endpoints

- `GET /health` - Health and readiness check.
- `GET /profiles` - List registered creator profiles.
- `POST /jobs/run` - Asynchronously scrape and index a creator.
- `POST /jobs/add-reel` - Asynchronously ingest reel URLs.
- `POST /jobs/saved-process` - Asynchronously process user saved posts.
- `GET /jobs/{id}` - Poll asynchronous job status and logs.
- `POST /query` - Perform grounded RAG queries with conversation history.

---

## Database Support

InstaRAG uses SQLAlchemy 2.0 for all relational and metadata operations. Supported database engines include:

- **SQLite (Default):** Local file-based database stored at `~/.instarag/instarag.db` (or `/data/config/instarag.db` inside Docker).
- **PostgreSQL / Supabase / Neon / AWS RDS:** Set `INSTARAG_DATABASE_URL` in your `.env`:
  ```env
  INSTARAG_DATABASE_URL=postgresql://user:password@host:5432/dbname
  ```

---

## Testing

Run the test suite with pytest:
```bash
uv sync --extra api
uv run pytest
```

---

## Documentation Index

For detailed technical specifications, refer to the documents in `docs/`:

- [Architecture and System Design](docs/architecture.md)
- [Comprehensive CLI Usage Guide](docs/usage.md)
- [HTTP REST API Reference](docs/api.md)
- [Indexer and Retrieval Pipeline](docs/modules/indexer_and_rag.md)
- [Analyzer Module Documentation](docs/modules/analyzer.md)
- [Scraper Module Documentation](docs/modules/scraper.md)
- [Downloader Module Documentation](docs/modules/downloader.md)
- [Filter Module Documentation](docs/modules/filter.md)
