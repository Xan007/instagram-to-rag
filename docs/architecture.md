# System Architecture: InstaRAG

## Overview
**InstaRAG** is a modular, multi-tenant/multi-account data pipeline and Retrieval-Augmented Generation (RAG) system. It ingests content from Instagram creator profiles, specific reel URLs, and user saved post exports (videos, carousels, infographics, and captions), transcribes and extracts dense factual knowledge, indexes semantic vectors into Pinecone, and manages user-scoped RAG agents (Groups) with sharing permissions.

```mermaid
flowchart TD
    subgraph Multi-Tenant Identity & Access
        U[User Accounts: `User`]
        G[RAG Agents / Collections: `Group`]
        S[Shared Access: `GroupShare`]
        U -->|Owns| G
        G -->|Shared with| S
        S -->|Grants access to| U
    end

    subgraph Global Deduplicated Pipeline
        IG[Global Creator Profiles: `IGProfile`] -->|Scrape All Posts| Scraper[Apify Scraper]
        ReelURL[Individual Reel URLs] --> ScraperURL[Apify Post Scraper / yt-dlp]
        SavedZip[User IG Data Export] --> SavedParser[Saved Posts Importer]
        
        Scraper --> Downloader[Media Downloader / yt-dlp]
        ScraperURL --> Downloader
        SavedParser --> Downloader
        
        Downloader --> Analyzer[Gemini Multimodal Analyzer / Whisper]
        Analyzer --> PostDB[(Relational DB: `Post` / PostgreSQL / SQLite / Supabase)]
        Analyzer --> Indexer[Pinecone Vector Indexer]
        Indexer --> Pinecone[(Pinecone Vector DB)]
    end

    subgraph Scoped Agents & Knowledge Retrieval
        G -->|Association via Interests / URLs| GP[Group Posts: `GroupPost`]
        GP -->|Filters by `post_id IN [...]`| QueryEngine[RAG Query Engine]
        QueryEngine -->|Vector Search with Metadata Filter| Pinecone
        Pinecone -->|Relevant Knowledge Chunks| GroundedGen[Grounded Answer Generator: Gemini]
        GroundedGen --> FinalAnswer[Grounded Answer with Source URLs]
    end
```

---

## Key Design Decisions

### 1. Global Deduplicated Extraction vs. Local Agent Scoping
- **Global Extraction:** Posts and Reels are scraped, analyzed, and embedded **exactly once** regardless of how many users track the creator or save the video.
- **Interests at Group Level:** Global scraping does not discard posts by topic. Instead, each user creates custom **Groups** (e.g. *Fitness*, *Nutrición*, *Recetas*) and uses LLM batch interest filtering to populate their group from existing global knowledge.

### 2. Database & Identity Agnosticism
- Built with **SQLAlchemy 2.0**: Switch seamlessly between local SQLite (`sqlite://...`), Supabase, Neon, or standard PostgreSQL (`postgresql://...`) via `INSTARAG_DATABASE_URL`.
- User references are stored as generic string IDs (`user_id`), allowing pluggable authentication (Clerk, Supabase Auth, Firebase, JWTs) without vendor lock-in.

### 3. Pinecone Vector Strategy
- Vectors are stored with rich metadata: `post_id`, `creator_username`, `url`, `type`, `original_description`, and `extracted_knowledge`.
- Queries scoped to a Group use Pinecone metadata filtering: `{"post_id": {"$in": [group_post_ids]}}`.

---

## Core Components

| Module | Responsibility |
|---|---|
| `storage` | SQLAlchemy models (`User`, `IGProfile`, `Post`, `Group`, `GroupPost`, `GroupShare`, `UserSavedPost`) & repository layer |
| `config` | User, Group, Global Profile, and Settings managers |
| `src.scraper` | Apify Actor integrations for profiles and individual post URLs |
| `src.downloader` | Direct CDN media downloader with yt-dlp fallback |
| `src.analyzer` | Gemini multimodal vision/audio understanding & Whisper fallback |
| `src.indexer` | Pinecone vector upsert & indexing |
| `src.rag` | Query engine with history condensation, score filtering, and citation annotations |
| `src.pipeline` | Orchestration layer for scraping, reel ingestion, saved posts, and group agent population |
| `src.api` | FastAPI REST API exposing background jobs, query endpoints, and OpenAPI docs |
