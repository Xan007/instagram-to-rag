# HTTP API (`src/api/` + `api.py`)

FastAPI service that exposes the InstaRAG pipeline to other projects and UIs.
The CLI (`main.py`) and the API share the same logic in `src/pipeline.py` —
there is no duplication.

## Run locally

```bash
uv sync --extra api
uv run api.py            # http://127.0.0.1:8000
```

Interactive OpenAPI docs: `http://localhost:8000/docs` (auto-generated, use it
as the contract for the UI project).

## Authentication

By default the API is open (local tool). Set `INSTARAG_API_KEY` to require an
`X-API-Key` header on every endpoint except `/health`.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET / PATCH | `/config` | Global settings (validated) |
| GET / POST | `/profiles` | List / create-or-update profiles |
| GET / PATCH / DELETE | `/profiles/{username}` | Inspect / edit / remove a profile |
| POST | `/profiles/{username}/reset` | Clear processed & failed history |
| POST | `/jobs/run` | Background pipeline for a profile |
| POST | `/jobs/add-reel` | Background ingestion of one or many reel/post URLs (`{urls: [...]}` or legacy `{url: "..."}`); uses `apify/instagram-scraper` for direct media URLs (plain HTTP download), falls back to yt-dlp per URL |
| POST | `/jobs/saved-process` | Background saved-posts processing |
| GET | `/jobs`, `/jobs/{id}` | Job list / status + log tail |
| POST | `/saved/import` | Upload `.zip` export or `saved_posts.json` (sync) |
| GET | `/saved/status` | Import/processing counters |
| POST | `/saved/reset` | Clear saved history |
| POST | `/query` | Grounded RAG query `{question, creator?, mode?, top_k?, min_score?, history?}` — `mode`: `grounded_plus` (default) or `strict`; `history`: client-owned prior turns `[{role: "user"\|"assistant", content}]` (max 12, stateless — send the full conversation each time) enabling follow-ups; low-confidence retrievals return an honest "nothing relevant" answer with closest links instead of a generic refusal. Each entry in `sources` carries `cited: true/false` |

Heavy operations return `202` with `{job_id, status_url}`. Jobs run serialized
(one at a time); poll `GET /jobs/{id}` until `status` is `completed` or
`failed`. The job payload includes a timestamped log tail produced by the
pipeline's progress callback (use `?log_limit=500` for more history).

Every job log line is **also echoed to the server console** prefixed with
`[job <id>]`, so `uv run api.py` shows live progress for add-reel, run and
saved-process without polling.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` / `APIFY_API_KEY` / `PINECONE_API_KEY` | — | Provider keys (same as CLI) |
| `INSTARAG_API_KEY` | unset | Protects the API when exposed |
| `INSTARAG_CORS_ORIGINS` | unset | Comma-separated origins allowed to call the API from a browser (e.g. `https://ui.tudominio.com,http://localhost:3000`). Unset = CORS disabled. |
| `INSTARAG_HOST` / `INSTARAG_PORT` | 127.0.0.1 / 8000 | Server bind |
| `INSTARAG_DATA_DIR` | `./data` | Media, backups and saved-posts state |
| `INSTARAG_CONFIG_DIR` | `~/.instarag` | Settings and profile states |

## Deploying

There is **no cloud coupling**: the app is a standard FastAPI container configured
entirely via environment variables (12-factor style). The same image runs on your
PC, any VPS, Fly.io, Render, GCP Cloud Run, Azure Container Apps, etc.

Run it anywhere Docker works:

```bash
docker build -t instarag-api .
docker run -p 8000:8000 \
  -v instarag-data:/data \
  -e GEMINI_API_KEY=... -e APIFY_API_KEY=... -e PINECONE_API_KEY=... \
  -e INSTARAG_API_KEY=<choose-a-secret> \
  instarag-api
```

Requirements on ANY host:

- **Persistence**: mount a volume at `/data` (container storage is ephemeral).
- **Long jobs**: keep a single instance/replica — jobs are serialized by design.
- **Security**: set `INSTARAG_API_KEY` whenever the port is reachable by others.
- **ffmpeg**: already included in the provided Dockerfile (yt-dlp needs it).

### Example: Azure Container Apps

One of many possible targets (consumption billing, scales to zero):

```bash
az login
RG=instarag-rg; LOCATION=westeurope; APP=instarag-api
ACR=instarag$(date +%s)acr

az group create -n $RG -l $LOCATION
az acr create -n $ACR -g $RG --sku Basic --admin-enabled true
az acr build --registry $ACR -t instarag:latest .

az containerapp env create -n instarag-env -g $RG -l $LOCATION

az containerapp create -n $APP -g $RG \
  --environment instarag-env \
  --image $ACR.azurecr.io/instarag:latest \
  --target-port 8000 --ingress external \
  --min-replicas 0 --max-replicas 1 \
  --secrets gemini-key=$GEMINI_API_KEY apify-key=$APIFY_API_KEY pinecone-key=$PINECONE_API_KEY \
  --env-vars GEMINI_API_KEY=secretref:gemini-key APIFY_API_KEY=secretref:apify-key \
             PINECONE_API_KEY=secretref:pinecone-key INSTARAG_API_KEY=<choose-a-secret> \
  --cpu 1.0 --memory 2Gi
```

For persistence across restarts, mount an **Azure Files** share at `/data`
(`az containerapp env storage set` + `--volume-mount`); alternative target with
identical steps: **App Service (Linux, custom container)**. Azure Functions is
NOT a good fit (jobs run for minutes/hours).
