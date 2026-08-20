# System Architecture: InstaRAG

## Overview
**InstaRAG** is a zero-cost, privacy-first, modular data pipeline and Retrieval-Augmented Generation (RAG) system. It transforms content from Instagram profiles and saved posts (videos, carousels, infographics, and text) into a structured vector database that can be queried with natural language, always citing original publication links.

## Saved Posts Flow
Instagram saved posts are imported from a personal data export (zip or `saved_posts.json`) and indexed without interest filtering:

```mermaid
flowchart LR
    A[Instagram Export .zip] -->|extract ONLY saved_posts.json, discard the rest| B[data/saved/saved_posts.json]
    B -->|parse: URL + caption + title| C[Dedup: skip IDs already in any profile or saved state]
    C -->|pending posts| D[Parallel workers x4: yt-dlp downloads reel media from each URL]
    D -->|instaloader session fallback for login-required reels| D
    D -->|mp4 video| E[Gemini multimodal knowledge extraction]
    C -->|caption fallback if media fetch fails| E
    E --> F[Pinecone Indexer under `saved` collection]
    F -->|processed/failed IDs| G[data/saved/state.json]
```
- The zip is never fully extracted: only `your_instagram_activity/saved/saved_posts.json` is read; all other personal data is discarded.
- Every saved post is processed regardless of profile interests.
- Posts already indexed through a profile are marked as processed (dedup by post shortcode).
- Download + analysis run in parallel with 4 workers (`--workers` to tune).

```mermaid
flowchart TD
    A[User CLI: `main.py run <username>`] --> B[Scraper Module: Apify / Instaloader]
    B -->|Batch Post Metadata| C[Batch Filter: Gemini 3.5 Flash Lite]
    C -->|Matching Post IDs| D[Parallel Downloader: ThreadPoolExecutor - 4 Workers]
    D -->|Asynchronous Streaming Queue| E[Multimodal Analyzer: Gemini Multi-Model Fallback]
    E -->|Structured Markdown Knowledge| F[Cleanup: Immediate Local File Deletion]
    E --> G[Pinecone Vector Indexer]
    G -->|Embed with gemini-embedding-001| H[(Pinecone Cloud Serverless Index)]
    G -->|JSON Backup| I[Local data/processed/]
    
    Q[User CLI: `main.py query <question>`] --> R[Query Engine: gemini-embedding-001]
    R -->|Semantic Vector Search| H
    H -->|Top-K Matching Knowledge Chunks| R
    R -->|Context + Question Prompt| J[Grounded Generator: Gemini Chat API]
    J --> K[Final Answer with Direct Instagram URLs]
```

## Performance & Resilience Features

1. **High-Speed Batch Filtering**:
   - Groups up to 40 posts per single Gemini API call to reduce latency from minutes to seconds.
2. **Parallel Downloads & Streaming Execution**:
   - Media items (videos, carousel slides, images) download concurrently with 4 worker threads.
   - As soon as the first download finishes, it streams directly into the Gemini Analyzer, keeping the GPU/API pipeline continuously fed.
3. **Multi-Model Fallback Chain**:
   - Handles `503 UNAVAILABLE` (model high demand) and `429` (rate limits) by automatically cascading across models: `gemini-3.5-flash-lite` -> `gemini-3.7-flash` -> `gemini-3.6-flash`.
4. **Zero-Cost Free-Tier Operations**:
   - Apify free monthly allowance for scraping.
   - Gemini API free tier for analysis & embeddings.
   - Pinecone Serverless free tier for vector storage.
5. **Strict Provenance Guarantee**:
   - Answers are synthesized strictly from retrieved creator posts with verified Instagram links.
