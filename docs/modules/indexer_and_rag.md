# Indexer & RAG Modules (`src/indexer/` & `src/rag/`)

## Vector Indexer (`src/indexer/pinecone_indexer.py`)
- Manages the cloud vector database index on Pinecone (`ig-profile-rag`).
- Uses **`gemini-embedding-001`** (3072 dimensions) to generate semantic vector representations of each post's extracted knowledge.
- Automatically provisions a Pinecone Serverless index (`aws / us-east-1`) if it does not already exist.
- Upserts metadata alongside vectors: `post_id`, `username`, `url`, `type`, `original_description`, and `extracted_knowledge`.
- Maintains a local JSON backup under `data/processed/<post_id>.json`.

## RAG Query Engine (`src/rag/query_engine.py`)
- Translates natural language user questions into vector embeddings.
- Performs cosine similarity search in Pinecone to retrieve top matching knowledge chunks (with optional creator filtering via `--creator`).
- Synthesizes grounded answers using **`gemini-3.6-flash`**.
- Guarantees strict provenance: every response includes verified direct links to the creator's original Instagram post.
