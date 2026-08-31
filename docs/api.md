# HTTP API (`src/api/`)

FastAPI service that exposes the InstaRAG pipelines, RAG query engine, and multi-tenant groups.

## Run locally

```bash
uv sync --extra api
uv run python -m src.api.main            # http://127.0.0.1:8000
```

Interactive OpenAPI docs: `http://localhost:8000/docs`

---

## Authentication & Multi-Tenancy

- **API Protection:** Set `INSTARAG_API_KEY` to require an `X-API-Key` header on all protected endpoints.
- **Identity-Agnostic:** Endpoints accept generic `user_id` / `user` identifiers, making it straightforward to connect Clerk, Supabase Auth, Firebase, or JWT middlewares.

---

## Endpoints Summary

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness and readiness probe |
| GET / PATCH | `/config` | Global app settings |
| GET / POST | `/profiles` | List / register global Instagram creator profiles |
| GET / DELETE | `/profiles/{username}` | Inspect or remove global profile |
| POST | `/jobs/run` | Scrape & index a creator globally |
| POST | `/jobs/add-reel` | Background ingestion of reel URLs |
| POST | `/jobs/saved-process` | Process imported saved posts |
| GET | `/jobs`, `/jobs/{id}` | Background job status & live progress logs |
| POST | `/saved/import` | Upload `.zip` Instagram export or `saved_posts.json` |
| POST | `/query` | Grounded RAG query (supports `creator`, `mode`, `history`, and `top_k`) |

---

## Cloud Deployment (Docker / Containers)

InstaRAG follows 12-factor cloud standards and runs anywhere Docker is supported:

```bash
docker compose up -d --build
```

### Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Gemini API key for embeddings and knowledge extraction |
| `PINECONE_API_KEY` | — | Pinecone API key |
| `APIFY_API_KEY` | — | Apify Actor token for Instagram scraping |
| `INSTARAG_DATABASE_URL` | `sqlite:////data/config/instarag.db` | Connection string for SQLite, PostgreSQL, Supabase, or Neon |
| `INSTARAG_API_KEY` | unset | Secret token for API key authentication |
| `INSTARAG_CORS_ORIGINS` | `*` | Allowed browser origins |
| `PORT` / `INSTARAG_PORT` | `8000` | HTTP port |
