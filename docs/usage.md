# CLI Usage Guide

## Prerequisites
Ensure your `.env` file contains your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key
APIFY_API_KEY=your_apify_api_token
PINECONE_API_KEY=your_pinecone_api_key
# Optional: PostgreSQL / Supabase / Neon connection
# INSTARAG_DATABASE_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres
```

---

## Command Reference

### 1. User Management
Manage local user accounts:
```bash
# Create a user account
python main.py user create juan
python main.py user create maria

# List accounts
python main.py user list
```

---

### 2. Instagram Creator Profiles (Global Ingestion)
Scrape and index creator profiles globally (deduplicated across all users):

```bash
# Register a creator profile
python main.py profile add nutricionista_experto

# Scrape all posts (no interest filter, indexed once into DB & Pinecone)
python main.py profile scrape nutricionista_experto --max-posts 100

# Incremental update (only scrapes posts newer than last run)
python main.py profile update nutricionista_experto

# List all registered creator profiles
python main.py profile list
```

---

### 3. Custom RAG Agents & Groups
Create topic-specific collections/agents (e.g. Food, Fitness, Biohacking), populate them, and share them:

```bash
# Create a new RAG Agent Group
python main.py group create RecetasSaludables --user juan --desc "Recetas altas en proteína y tips de cocina"

# Populate the group from an indexed creator, applying interest filtering
python main.py group add-from-profile RecetasSaludables nutricionista_experto --interests "recetas, comidas, desayunos" --user juan

# Add an individual Reel by URL or Shortcode ID directly to the group
python main.py group add-post RecetasSaludables "https://www.instagram.com/reel/C8xyz123/" --user juan

# List your groups (shows owned and shared groups)
python main.py group list --user juan

# Share your agent with another account
python main.py group share RecetasSaludables maria --user juan
```

---

### 4. Saved Posts (Instagram Data Export)
Import and index saved posts per user account:

```bash
# Import your Instagram data export (zip or saved_posts.json)
python main.py saved import ruta/a/tu_export.zip --user juan

# Download, extract knowledge, and index pending saved posts
python main.py saved process --user juan --workers 4
```

---

### 5. Ingesting Reels by URL
Ingest standalone Reels without an associated profile:
```bash
python main.py add-reel https://www.instagram.com/reel/ABC/ https://www.instagram.com/p/DEF/
```

---

### 6. Querying & Interactive Chat
Ask questions across global knowledge or scoped to a custom Group Agent:

```bash
# Query a specific Group Agent
python main.py query "¿Qué opciones de desayuno rápido recomienda?" --group RecetasSaludables --user juan

# Query across a specific creator
python main.py query "¿Qué opina del ayuno intermitente?" --creator nutricionista_experto

# Query in strict mode (no general knowledge fallback)
python main.py query "..." --group RecetasSaludables --user juan --mode strict --top-k 10

# Interactive multi-turn chat with an Agent (supports follow-ups like "¿y para principiantes?")
python main.py chat --group RecetasSaludables --user maria
```
