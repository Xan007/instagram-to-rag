# Implementation Plan: InstaRAG

## Goal Description
**InstaRAG** is a zero-cost, locally-run (with cloud APIs) data pipeline designed to extract knowledge from specific Instagram profiles and saved posts and build an interactive RAG (Retrieval-Augmented Generation) query engine. 

The system will:
1. **Scrape** metadata (descriptions, hashtags, URLs) from an Instagram profile locally (with future Apify integration).
2. **Filter** posts based on user-configured interests (e.g., "food, diet, recipes") using LLM-based text analysis. If the text is inconclusive, it will download the video to be sure.
3. **Download** the media locally for processing.
4. **Analyze** the video/audio to extract knowledge. It will use the **Gemini API** for video analysis, or offer a configurable option for **local Whisper** transcription if only the audio matters.
5. **Index** the extracted text into **Pinecone** (free tier), using either Gemini or local HuggingFace embeddings.
6. **Query** the knowledge base using a pure RAG approach, guaranteeing answers are based solely on the creator's content and always include the link to the original post.

## Multi-Profile Configuration & Caching
The pipeline supports multiple profiles. Each profile has its own configuration (e.g., specific interests) and maintains a history of processed posts (`processed_ids`). When the scraper runs, it will skip posts that have already been processed to avoid redundant downloading, API calls, and indexing.

## Proposed Architecture & Changes

We are building a modular Python CLI application.

### 1. Configuration & CLI
Uses `Typer` for the command line. Configuration is divided into global settings and per-profile configurations.
#### `main.py`
Entry point for the CLI. Commands: `profile add`, `profile list`, `run`, `query`.
#### `config/settings.py`
Handles global settings (e.g., embedding provider, default engine).
#### `config/profiles.py`
Handles saving/loading individual profile rules (username, specific interests, limits) and their tracking states (list of already scraped post IDs).

---

### 2. Scraping Module
Initially implemented entirely locally.
#### `src/scraper/base.py`
Abstract class defining the contract (e.g., `get_posts(username, limit, skip_ids)`).
#### `src/scraper/local_instaloader.py`
Uses `instaloader` to fetch post metadata without downloading video yet, yielding posts one by one.

---

### 3. Filtering & Download
Logic to decide if a post matches the criteria.
#### `src/filter/interest_filter.py`
Uses Gemini (text-only) to evaluate if the post description/hashtags align with the profile's specific interests. Returns `YES`, `NO`, or `UNSURE`.
#### `src/downloader/media_downloader.py`
Downloads the `.mp4` files for posts marked as `YES` or `UNSURE`.

---

### 4. Media Analysis (Gemini / Whisper)
#### `src/analyzer/gemini_analyzer.py`
Uploads the local `.mp4` to Gemini API, prompts for knowledge extraction, and returns structured text. Deletes local file afterward.
#### `src/analyzer/whisper_analyzer.py`
Extracts `.mp3` from `.mp4` using `ffmpeg`, runs local Whisper transcription, and formats the output.

---

### 5. Indexing & RAG
#### `src/indexer/pinecone_indexer.py`
Chunks the extracted transcripts, embeds them (via Local HuggingFace or Gemini), and upserts into a Pinecone index.
#### `src/rag/query_engine.py`
Takes user questions, fetches relevant context from Pinecone, and uses Gemini to answer *only* based on the context, appending the source URLs.

## Verification Plan

### Automated Tests
- No tests for the moment, as requested by the user. 

### Manual Verification
1. Add a profile: `uv run main.py profile add <username> --interests "diet, recipes"`
2. Run the pipeline: `uv run main.py run <username>`
3. Verify that only relevant posts are downloaded, transcribed, and indexed.
4. Run the pipeline again and verify it skips the already processed posts.
5. Query: `uv run main.py query "What is the recommended diet?"` and ensure the answer includes the correct Instagram URL.
