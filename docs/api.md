# HTTP REST API Reference (`src/api/`)

The InstaRAG HTTP service provides REST endpoints for managing background ingestion tasks, retrieving knowledge, and querying custom RAG agents.

---

## Running the API Server

### Local Development

```bash
uv sync --extra api
uv run python -m src.api.main
```

The server binds to `http://127.0.0.1:8000` by default. Interactive OpenAPI documentation is accessible at `http://127.0.0.1:8000/docs`.

### Docker Deployment

```bash
docker compose up -d --build
```

---

## Authentication and Security

- **API Protection:** Set the `INSTARAG_API_KEY` environment variable. When set, all requests (except `/health`) must include the `X-API-Key: <your_secret_key>` header.
- **Identity Decoupling:** Endpoints accept opaque `user_id` or `username` parameters, allowing integration with external identity providers (such as Clerk, Supabase Auth, Firebase, or custom JWT middlewares).

---

## Endpoint Summary

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness and readiness check. Returns `{"status": "ok"}`. |
| GET / PATCH | `/config` | Inspect and update global pipeline settings (`audio_only`, `engine`, `embed_provider`). |
| GET / POST | `/profiles` | List registered creator profiles or register a new creator profile. |
| GET / DELETE | `/profiles/{username}` | Retrieve details or delete a registered profile. |
| POST | `/profiles/{username}/reset` | Reset processing history for a creator profile. |
| POST | `/jobs/run` | Submit an asynchronous background job to scrape and index a creator. |
| POST | `/jobs/add-reel` | Submit an asynchronous background job to ingest reel URLs. |
| POST | `/jobs/saved-process` | Submit an asynchronous background job to process user saved posts. |
| GET | `/jobs` | List recent background jobs and worker queue status. |
| GET | `/jobs/{job_id}` | Inspect job status, execution metrics, and timestamped log tail. |
| POST | `/saved/import` | Upload an Instagram data export (`.zip` or `saved_posts.json`). |
| GET | `/saved/status` | Retrieve import counters and pending post stats. |
| POST | `/query` | Execute a grounded RAG query with optional multi-turn conversation history. |

---

## Asynchronous Background Jobs

Resource-heavy operations (`/jobs/run`, `/jobs/add-reel`, and `/jobs/saved-process`) return HTTP status `202 Accepted` with a JSON payload:

```json
{
  "job_id": "a1b2c3d4",
  "status_url": "/jobs/a1b2c3d4"
}
```

Clients should poll `GET /jobs/{job_id}` until `status` transitions to `completed` or `failed`. The response includes a live log tail from the pipeline worker.

---

## RAG Query Payload Specification

```json
POST /query
Content-Type: application/json

{
  "question": "What protein sources does this creator recommend?",
  "creator": "fitness_coach",
  "mode": "grounded_plus",
  "top_k": 6,
  "min_score": 0.35,
  "history": [
    {"role": "user", "content": "Tell me about diet recommendations."},
    {"role": "assistant", "content": "The creator recommends lean meats, eggs, and Greek yogurt."}
  ]
}
```

### Response Attributes

- `answer` (string): Synthesized answer with `[Source N]` citation tags.
- `sources` (array): Retrieved post objects containing `creator`, `url`, `score`, and a boolean `cited` flag indicating if the model used that specific post in the final answer.
- `mode` (string): `grounded_plus` or `strict`.
- `standalone_question` (string, optional): The condensed standalone query generated from conversation history.
