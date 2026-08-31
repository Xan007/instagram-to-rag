<div align="center">

# InstaRAG

[![Python](https://img.shields.io/badge/Python-3.12%20|%203.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-embedding%20%2B%20analysis-4285F4?logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![Pinecone](https://img.shields.io/badge/Pinecone-vector%20DB-000000?logo=pinecone&logoColor=white)](https://www.pinecone.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-HTTP%20API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

</div>

**InstaRAG** is a modular, multi-account Instagram knowledge extraction pipeline and Retrieval-Augmented Generation (RAG) platform. It ingests Instagram creator profiles, individual reels, and user saved post exports, extracts dense factual knowledge via Gemini multimodal analysis, indexes deduplicated semantic vectors into Pinecone, and allows users to build, query, and share custom topic-scoped **RAG Agents (Groups)** (e.g. *Fitness*, *Recetas*, *Biohacking*).

---

## 🌟 Key Capabilities

- **👥 Multi-Account & Scoped RAG Agents (Groups):** Create distinct agents per account, assign specific posts by interest or direct URL, and share agents with other accounts with read permissions.
- **⚡ Global Knowledge Deduplication:** Ingests creator posts and reels globally once. N users tracking the same creator or saving the same video never causes duplicate extraction or vector clutter.
- **🌐 Database & Auth Agnostic:** Backed by SQLAlchemy 2.0. Switch between SQLite, PostgreSQL, Supabase, or Neon via a single `INSTARAG_DATABASE_URL` environment variable.
- **📊 Dense Multimodal Knowledge:** Structured fact sheets, numbers (sets×reps, grams, seconds), on-screen text, and spoken transcripts extracted from videos and carousel slides.
- **🎯 Provenance & Dual RAG Modes:** Source citations `[Source N]` with direct Instagram URLs, confidence thresholds, and dual answer modes (`grounded_plus` default / `strict`).
- **💬 Multi-Turn Follow-Ups:** Stateless chat history condensation (e.g., handles questions like "¿y para principiantes?").
- **☁️ Cloud & Docker Ready:** Containerized with healthchecks, non-root user, dynamic `$PORT` detection, and `docker-compose.yml`.

---

## 🛠️ Quickstart

### 1. Installation
```bash
uv sync --extra api
```

### 2. Configuration
Copy `.env.example` to `.env` and fill in your keys:
```env
GEMINI_API_KEY=your_gemini_api_key
PINECONE_API_KEY=your_pinecone_api_key
APIFY_API_KEY=your_apify_api_key
# Optional (defaults to SQLite):
# INSTARAG_DATABASE_URL=postgresql://postgres:pass@db.xxx.supabase.co:5432/postgres
```

---

## 💻 CLI Usage

```bash
# 1. Manage accounts
python main.py user create juan
python main.py user create maria

# 2. Scrape & index a creator globally
python main.py profile add nutricionista_experto
python main.py profile scrape nutricionista_experto --max-posts 100
python main.py profile update nutricionista_experto  # incremental update

# 3. Create & populate a scoped RAG Agent group
python main.py group create RecetasSaludables --user juan --desc "Recetas de cocina saludable"
python main.py group add-from-profile RecetasSaludables nutricionista_experto --interests "recetas, desayunos, comidas" --user juan
python main.py group add-post RecetasSaludables "https://www.instagram.com/reel/C8xyz123/" --user juan
python main.py group share RecetasSaludables maria --user juan

# 4. Import user saved posts from IG export
python main.py saved import export.zip --user juan
python main.py saved process --user juan

# 5. Query and Chat
python main.py query "¿Qué opciones de desayuno recomienda?" --group RecetasSaludables --user juan
python main.py chat --group RecetasSaludables --user maria
```

---

## 🚀 HTTP API & Deployment

Run the FastAPI service:
```bash
uv run python -m src.api.main
# Interactive OpenAPI Docs available at http://127.0.0.1:8000/docs
```

Run with Docker:
```bash
docker compose up -d --build
```

---

## 📚 Documentation

- [Architecture & Design](docs/architecture.md)
- [CLI Usage Guide](docs/usage.md)
- [HTTP API Reference](docs/api.md)
- [Indexer and RAG Pipeline](docs/modules/indexer_and_rag.md)
