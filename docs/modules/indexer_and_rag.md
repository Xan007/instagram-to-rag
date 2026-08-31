# Indexer and RAG Retrieval Pipeline

This document details the vector indexing strategy in Pinecone and the retrieval and answer generation pipeline implemented in InstaRAG.

---

## 1. Vector Indexer (`src/indexer/pinecone_indexer.py`)

### Embedding Model Configuration
- **Model:** `gemini-embedding-001` via Google GenAI SDK.
- **Embedding Dimension:** 3,072.
- **Distance Metric:** Cosine similarity (`cosine`).
- **Pinecone Specification:** Serverless index hosted on AWS (`us-east-1`).

### Deduplicated Upsert Protocol
Each Instagram post is embedded and upserted **once globally**. Vector identifiers follow the deterministic format `{creator}_{post_id}` or `{post_id}`.

### Vector Metadata Schema
Each vector in Pinecone includes the following metadata payload:

| Metadata Field | Type | Description |
|---|---|---|
| `post_id` | string | Instagram shortcode identifier (e.g., `C8xyz123`). |
| `creator_username` | string | Instagram creator handle. |
| `url` | string | Original Instagram post URL. |
| `type` | string | Media type (`Post`, `Reel`, `Sidecar`, `Video`, or `Image`). |
| `original_description` | string | Text caption excerpt (truncated to 1,000 characters). |
| `extracted_knowledge` | string | Structured markdown knowledge extracted by Gemini (truncated to 8,000 characters). |

---

## 2. Query Engine (`src/rag/query_engine.py`)

### Scoped Agent Retrieval
When querying a custom RAG Agent (Group), the query engine retrieves the member `post_id` list from the database and applies a Pinecone metadata filter:

```python
filter = {"post_id": {"$in": ["C8xyz123", "D9abc456", "E0def789"]}}
```

When querying across a specific creator:
```python
filter = {"creator_username": {"$eq": "target_creator"}}
```

### Multi-Turn Conversational Condensation
For conversational interactions where the user submits follow-up questions (such as "what about vegetarians?"), the engine passes the conversation history to Gemini to generate an autonomous standalone query before generating embeddings.

### Dual Response Modes

1. **`grounded_plus` (Default Mode):**
   - Answers strictly using the retrieved creator context and attributes facts using `[Source N]` tags.
   - If general context is necessary to provide a complete answer, appends a distinct, labeled section:
     ```
     ---
     General (not from creators):
     [Factual general knowledge summary]
     ```
   - Never attributes general knowledge to the creators.

2. **`strict` Mode:**
   - Absolute provenance. If the retrieved context does not contain the answer, the model returns a direct refusal stating that the creators have not covered the topic.

---

## 3. Citation Annotation
The query engine parses the generated answer text for citation markers (`[Source 1]`, `[Source 2]`) and annotates each returned source object with `cited: true` or `cited: false`. This allows client user interfaces to highlight only the sources that directly contributed to the response.
