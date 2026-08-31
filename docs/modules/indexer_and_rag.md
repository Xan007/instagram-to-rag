# Indexer and RAG Architecture

## Indexer (`src/indexer/pinecone_indexer.py`)

- **Model:** `gemini-embedding-001` (dimension 3072, metric `cosine`).
- **Serverless Spec:** AWS `us-east-1`.
- **Deduplication:** Each Instagram post is indexed **once globally**. The vector ID format is `{creator}_{post_id}` or `{post_id}`.
- **Stored Metadata per Vector:**
  - `post_id`: Shortcode identifier of the Instagram post.
  - `creator_username`: Instagram creator username.
  - `url`: Original Instagram URL.
  - `type`: Content type (`Post`, `Reel`, `Sidecar`, `Video`, `Image`).
  - `original_description`: Post caption snippet (up to 1,000 characters).
  - `extracted_knowledge`: Structured markdown knowledge summary (up to 8,000 characters).

---

## Query Engine (`src/rag/query_engine.py`)

### 1. Scoped Agent Filtering
When querying a custom Group Agent, Pinecone applies metadata filtering:
```python
filter = {"post_id": {"$in": ["C8xyz123", "D9abc456", ...]}}
```
When querying across a creator:
```python
filter = {"creator_username": {"$eq": "nutricionista_experto"}}
```

### 2. Multi-Turn Conversation Condensation
Follow-up questions are resolved in a stateless manner: prior message turns are passed to Gemini to generate an autonomous standalone retrieval query before embedding.

### 3. Dual Response Modes
- **`grounded_plus` (Default):** Answers strictly using the retrieved context from creator posts with `[Source N]` citations. Appends a clearly separated general-knowledge section only if it adds necessary context.
- **`strict`:** Pure creator provenance. Refuses to answer if the creator's posts do not contain the answer.
