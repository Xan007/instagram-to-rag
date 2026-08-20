# CLI Usage Guide

## Prerequisites
Ensure your `.env` file contains your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key
APIFY_API_KEY=your_apify_api_token
PINECONE_API_KEY=your_pinecone_api_key
```

## Commands

### 1. Profile Management
Add creators and specify tailored topics of interest:
```bash
# Add or update a profile
uv run python main.py profile add bejaranofit --interests "recetas, dieta, comida" --max-posts 50

# List all configured profiles and their progress
uv run python main.py profile list
```

### 2. Knowledge Ingestion Pipeline
Run the extraction pipeline on a profile:
```bash
uv run python main.py run bejaranofit
```
- Scrapes metadata from Instagram via Apify.
- Filters posts matching your defined interests.
- Downloads images, carousel slides, and videos.
- Extracts dense factual knowledge using Gemini multimodal vision & audio understanding.
- Indexes semantic vectors and full metadata into Pinecone.
- Saves a backup JSON locally in `data/processed/`.
- Deletes heavy media files immediately.

### 3. Querying the Knowledge Base (RAG)
Ask questions in natural language and receive grounded answers with direct links:
```bash
# Query across all creators
uv run python main.py query "¿Cómo preparar una pasta alta en proteínas?"

# Query filtered by a specific creator
uv run python main.py query "¿Qué ejercicios recomienda para espalda?" --creator bejaranofit
```
