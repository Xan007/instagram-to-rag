import logging
import re
from typing import Any, Dict, List, Optional
from rank_bm25 import BM25Okapi
from storage.db import get_session
import storage.repositories as repo

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


class HybridRetriever:
    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        pinecone_matches: List[Dict[str, Any]],
        creator: Optional[str] = None,
        post_ids: Optional[List[str]] = None,
        top_k: int = 6,
    ) -> List[Dict[str, Any]]:
        db = get_session()
        try:
            if post_ids is not None:
                all_posts = [repo.get_post(db, pid) for pid in post_ids]
                all_posts = [p for p in all_posts if p is not None]
            elif creator:
                all_posts = repo.list_posts(db, creator_username=creator)
            else:
                all_posts = repo.list_posts(db)
        finally:
            db.close()

        if not all_posts and not pinecone_matches:
            return []

        doc_by_id: Dict[str, Dict[str, Any]] = {}
        for p in all_posts:
            doc_by_id[p.id] = {
                "id": p.id,
                "score": 0.0,
                "metadata": {
                    "post_id": p.id,
                    "creator_username": p.creator_username,
                    "url": p.url,
                    "type": p.type,
                    "original_description": p.description,
                    "extracted_knowledge": p.extracted_knowledge,
                },
            }

        for m in pinecone_matches:
            meta = m.get("metadata", {})
            pid = meta.get("post_id") or m.get("id")
            if pid and pid not in doc_by_id:
                doc_by_id[pid] = m

        valid_docs = list(doc_by_id.values())
        if not valid_docs:
            return pinecone_matches[:top_k]

        tokenized_corpus = [
            tokenize(
                f"{d['metadata'].get('original_description', '')} {d['metadata'].get('extracted_knowledge', '')}"
            )
            for d in valid_docs
        ]
        tokenized_query = tokenize(query)

        bm25_ranked_ids: List[str] = []
        if any(tokenized_corpus) and tokenized_query:
            bm25 = BM25Okapi(tokenized_corpus)
            bm25_scores = bm25.get_scores(tokenized_query)
            scored_docs = [
                (valid_docs[i]["metadata"].get("post_id") or valid_docs[i]["id"], score)
                for i, score in enumerate(bm25_scores)
                if score > 0.0
            ]
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            bm25_ranked_ids = [doc_id for doc_id, _ in scored_docs]

        dense_ranked_ids: List[str] = [
            m.get("metadata", {}).get("post_id") or m.get("id")
            for m in pinecone_matches
        ]

        rrf_scores: Dict[str, float] = {}

        for rank, doc_id in enumerate(dense_ranked_ids):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (self.rrf_k + (rank + 1)))

        for rank, doc_id in enumerate(bm25_ranked_ids):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (self.rrf_k + (rank + 1)))

        sorted_doc_ids = sorted(rrf_scores.keys(), key=lambda did: rrf_scores[did], reverse=True)

        final_matches: List[Dict[str, Any]] = []
        for did in sorted_doc_ids[:top_k]:
            doc = doc_by_id.get(did)
            if doc:
                normalized_score = min(1.0, rrf_scores[did] * 30.0)
                final_matches.append({
                    "id": doc.get("id", did),
                    "score": normalized_score,
                    "metadata": doc.get("metadata", {}),
                })

        return final_matches if final_matches else pinecone_matches[:top_k]
