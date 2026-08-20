# Implementation Plan: InstagramProfile2RAG

## Goal Description
**InstagramProfile2RAG** is a zero-cost, locally-run (with cloud APIs) data pipeline designed to extract knowledge from specific Instagram profiles and build an interactive RAG (Retrieval-Augmented Generation) query engine. 

The system will:
1. **Scrape** metadata (descriptions, hashtags, URLs) from an Instagram profile locally (with future Apify integration).
2. **Filter** posts based on user-configured interests (e.g., "food, diet, recipes") using LLM-based text analysis. If the text is inconclusive, it will download the video to be sure.
3. **Download** the media locally for processing.
4. **Analyze** the video/audio to extract knowledge. It will use the **Gemini API** for video analysis, or offer a configurable option for **local Whisper** transcription if only the audio matters.
5. **Index** the extracted text into **Pinecone** (free tier).
6. **Query** the knowledge base using a pure RAG approach, guaranteeing answers are based solely on the creator's content and always include the link to the original post.

## User Review Required
> [!IMPORTANT]
> **Language & Architecture Decision**: I strongly recommend **Python** for this project. It has the best ecosystem for CLI applications (`Typer`), scraping (`Instaloader`), AI (`google-generativeai`, `whisper`), and Vector DBs (`pinecone-client`). 
> Are you comfortable proceeding with Python?

> [!WARNING]
> **Instagram Scraping Constraints**: Instagram aggressively blocks scraping. For the local phase, we will use `instaloader`, which may require you to log in using a burner Instagram account to avoid IP bans. When transitioning to Apify later, this will be handled by their proxies.

## Open Questions
> [!NOTE]
> 1. **Embeddings Model**: To index data into Pinecone, we need an embedding model. Should we use Gemini's embedding model (since you are already using Gemini for analysis) or an open-source local one (like `HuggingFace/all-MiniLM-L6-v2`) to save API calls?
> 2. **Folder Generation**: You requested that I generate the folders immediately. As per my strict planning constraints, I have created this plan first. If you click **Proceed** or explicitly approve, I will instantly run the commands to generate the entire project structure!

## Proposed Architecture & Changes

We will build a modular Python CLI application.

### 1. Configuration & CLI
Uses `Typer` for the command line and `yaml` or `json` for saving configurations locally.
#### [NEW] `main.py`
Entry point for the CLI. Commands: `config`, `run`, `query`.
#### [NEW] `config/settings.py`
Handles loading/saving user interests, max posts, analysis preferences (Gemini vs Whisper).

---

### 2. Scraping Module
Initially implemented entirely locally.
#### [NEW] `modules/scraper/base_scraper.py`
Abstract class defining the contract (e.g., `get_posts(username, limit)`).
#### [NEW] `modules/scraper/local_instaloader.py`
Uses `instaloader` to fetch post metadata without downloading video yet.

---

### 3. Filtering & Download
Logic to decide if a post matches the criteria.
#### [NEW] `modules/filter/interest_filter.py`
Uses Gemini (text-only) to evaluate if the post description/hashtags align with user interests. Returns `YES`, `NO`, or `UNSURE`.
#### [NEW] `modules/downloader/media_downloader.py`
Downloads the `.mp4` files for posts marked as `YES` or `UNSURE`.

---

### 4. Media Analysis (Gemini / Whisper)
#### [NEW] `modules/analyzer/gemini_analyzer.py`
Uploads the local `.mp4` to Gemini API, prompts for knowledge extraction, and returns structured text. Deletes local file afterward.
#### [NEW] `modules/analyzer/whisper_analyzer.py`
Extracts `.mp3` from `.mp4` using `ffmpeg`, runs local Whisper transcription, and formats the output.

---

### 5. Indexing & RAG
#### [NEW] `modules/indexer/pinecone_indexer.py`
Chunks the extracted transcripts, embeds them, and upserts into a Pinecone index.
#### [NEW] `modules/rag/query_engine.py`
Takes user questions, fetches relevant context from Pinecone, and uses Gemini to answer *only* based on the context, appending the source URLs.

## Verification Plan

### Automated Tests
- Unit tests for the `interest_filter` to ensure it correctly classifies sample descriptions.
- Mocking tests for the `scraper` and `analyzer` to verify data flow without hitting API limits.
Command: `pytest tests/`

### Manual Verification
1. Run `python main.py config set --interests "diet, recipes" --audio-only true --engine local_whisper`.
2. Run `python main.py run <instagram_username> --limit 5`.
3. Verify that only relevant posts are downloaded, transcribed, and indexed.
4. Run `python main.py query "What is the recommended diet?"` and ensure the answer includes the correct Instagram URL.
