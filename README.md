<div align="center">

# InstaRAG

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-embedding%20%2B%20analysis-4285F4?logo=googlegemini&logoColor=white)](https://ai.google.dev/)

</div>

InstaRAG is a CLI tool that extracts knowledge from Instagram profiles and saved posts, then indexes it into a Pinecone vector database for retrieval-augmented generation (RAG).

## Features

- Analyze Instagram profiles: posts, reels, and carousels.
- Import your Instagram data export (saved posts) and process all of them.
- Analyze video content with Gemini vision and transcribe audio with Whisper.
- Download media directly from actor-provided CDN URLs, or yt-dlp when only a post URL is available.
- Ask questions in natural language with grounded answers and source citations.

## Tech Stack

- Python 3.14 and uv
- Google Gemini (analysis and embeddings)
- Pinecone (vector database)
- yt-dlp, Apify (Instagram content)
- faster-whisper (audio transcription)
- Typer + Rich (CLI)

## Installation

```bash
uv sync
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

```
GEMINI_API_KEY=your_key
PINECONE_API_KEY=your_key
PINECONE_INDEX_NAME=instarag
```

For the `.exe`, each user should configure their own keys in one of these locations:
- `.\.env` (same folder where `instarag.exe` is located)
- `~/.instarag/.env` (recommended for persistent per-user setup)
- System environment variables

Global settings and profiles are stored in `~/.instarag`.

## Usage

```bash
# Add a profile and process it
instarag profile add --username <your_target> --mode gemini
instarag run --username <your_target>

# Process saved posts from an Instagram data export
instarag saved import export.zip
instarag saved process

# Ask questions
instarag query "your question here" --creator <your_target>
```

## Commands

| Command | Description |
| --- | --- |
| `profile` | Manage Instagram profiles |
| `run` | Extract and index knowledge from a profile |
| `saved` | Import and process saved posts |
| `add-reel` | Add one or more reels/posts by URL |
| `query` | Ask the knowledge base |
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