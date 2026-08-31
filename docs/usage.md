# Command-Line Interface (CLI) Usage Guide

This guide covers all available command-line operations for managing user accounts, ingesting content from Instagram creator profiles, organizing content into scoped RAG Agent groups, and querying the knowledge base.

---

## Configuration and Prerequisites

Ensure your environment variables are configured in `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
PINECONE_API_KEY=your_pinecone_api_key
APIFY_API_KEY=your_apify_api_key

# Optional: PostgreSQL / Supabase / Neon connection string (defaults to SQLite if unset)
# INSTARAG_DATABASE_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres

# Optional: Default active user for CLI commands
# INSTARAG_USER=john
```

---

## 1. Account Management (`user`)

InstaRAG supports multi-tenant operations. All groups and saved post imports are owned by user accounts.

```bash
# Create new user accounts
python main.py user create john
python main.py user create alice

# List all registered accounts
python main.py user list
```

---

## 2. Global Instagram Profiles (`profile`)

Creator profiles are registered and ingested globally. Once ingested, the content is available for any user to include in custom groups without duplicate extraction.

```bash
# Register an Instagram creator profile globally
python main.py profile add fitness_coach

# Ingest all posts for a creator
python main.py profile scrape fitness_coach --max-posts 100

# Perform an incremental update (only scrapes posts newer than the previous scrape timestamp)
python main.py profile update fitness_coach

# List all globally registered profiles and their scrape status
python main.py profile list
```

---

## 3. Scoped RAG Agents and Groups (`group`)

Groups act as dedicated RAG agents. Users can create groups for specific domains (such as Nutrition, Workout Routines, or Productivity Tips), populate them with relevant posts, and share them with other users.

```bash
# Create a new scoped RAG Agent group
python main.py group create HighProteinDiet --user john --desc "Diet plans and high protein meal prep ideas"

# Populate the group from an indexed creator by applying an interest filter
python main.py group add-from-profile HighProteinDiet fitness_coach --interests "recipes, high protein, breakfast, diet" --user john

# Add a specific post or reel by URL or Shortcode ID directly to the group
python main.py group add-post HighProteinDiet "https://www.instagram.com/reel/C8xyz123/" --user john

# Share the agent with another account
python main.py group share HighProteinDiet alice --user john

# List groups accessible to an account (both owned and shared)
python main.py group list --user alice
```

---

## 4. Saved Posts Ingestion (`saved`)

Users can import and index their personal saved post exports from Instagram:

```bash
# Import an Instagram data export (ZIP file or saved_posts.json)
python main.py saved import /path/to/instagram-export.zip --user john

# Process, transcribe, and index pending saved posts
python main.py saved process --user john --workers 4

# Process captions only (skips media download)
python main.py saved process --user john --caption-only
```

---

## 5. Standalone Reel Ingestion (`add-reel`)

Ingest individual posts or reels without associating them with a full creator profile:

```bash
# Ingest one or more URLs
python main.py add-reel https://www.instagram.com/reel/ABC123/ https://www.instagram.com/p/DEF456/

# Associate with a creator name
python main.py add-reel https://www.instagram.com/reel/ABC123/ --creator fitness_coach
```

---

## 6. Querying and Conversational Chat (`query` and `chat`)

Ask questions across global knowledge or restrict answers to a specific custom RAG Agent:

```bash
# Query a specific custom Group Agent
python main.py query "What are the recommended breakfast meal prep options?" --group HighProteinDiet --user john

# Query across a specific creator profile
python main.py query "What warm-up routine does this creator recommend?" --creator fitness_coach

# Query with strict provenance (refuses if information is not present in creator posts)
python main.py query "What is the recommended daily creatine dosage?" --creator fitness_coach --mode strict

# Adjust retrieval threshold and top candidates
python main.py query "..." --group HighProteinDiet --user john --top-k 10 --min-score 0.4

# Interactive multi-turn chat (supports follow-up questions like "what about vegetarians?")
python main.py chat --group HighProteinDiet --user alice
```
