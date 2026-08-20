<div align="center">

# InstaRAG

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-package%20manager-6E4089?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-embedding%20%2B%20analysis-4285F4?logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![Pinecone](https://img.shields.io/badge/Pinecone-vector%20database-000000?logo=pinecone&logoColor=white)](https://www.pinecone.io/)
[![faster-whisper](https://img.shields.io/badge/faster--whisper-audio%20transcription-23A9E0?logo=openai&logoColor=white)](https://github.com/SYSTRAN/faster-whisper)

</div>

InstaRAG is a CLI tool that extracts knowledge from Instagram profiles and saved posts, then indexes it into a Pinecone vector database for retrieval-augmented generation (RAG).

## Features

- Analyze Instagram profiles: posts, reels, and carousels.
- Import your Instagram data export (saved posts) and process all of them.
- Analyze video content with Gemini vision and transcribe audio with Whisper.
- Download media with yt-dlp, with an instaloader fallback using your browser session.
- Ask questions in natural language with grounded answers and source citations.

## Tech Stack

- Python 3.14 and uv
- Google Gemini (analysis and embeddings)
- Pinecone (vector database)
- yt-dlp, instaloader, Apify (Instagram content)
- faster-whisper (audio transcription)
- Typer + Rich (CLI)

## Installation

```bash
uv sync
```

## Configuration

Create a `.env` file:

```
GEMINI_API_KEY=your_key
PINECONE_API_KEY=your_key
PINECONE_INDEX_NAME=instarag
```

Global settings and profiles are stored in `~/.instarag`.

## Usage

```bash
# Add a profile and process it
instarag profile add --username bejaranofit --mode gemini
instarag run --username bejaranofit

# Process saved posts from an Instagram data export
instarag saved import export.zip
instarag saved process

# Optional: instaloader session from browser cookies (for media downloads)
instarag auth-session your_username

# Ask questions
instarag query "workout routine for muscle gain" --creator bejaranofit
```

## Commands

| Command | Description |
| --- | --- |
| `profile` | Manage Instagram profiles |
| `run` | Extract and index knowledge from a profile |
| `saved` | Import and process saved posts |
| `auth-session` | Create an instaloader session from browser cookies |
| `query` | Ask the knowledge base |
| `config` | Configure global settings |

## Documentation

- [Usage guide](docs/usage.md)
- [Architecture](docs/architecture.md)
- [Indexer and RAG](docs/modules/indexer_and_rag.md)