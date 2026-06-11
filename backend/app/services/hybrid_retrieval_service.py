from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.embedding_service import embedding_service
from app.services.qdrant_service import qdrant_service


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


class HybridRetrievalService:
    """Combines Qdrant vector search with PostgreSQL FTS using Reciprocal Rank Fusion."""

    def search(
        self,
        query: str,
        tenant_id: str,
        allowed_classifications: list[str],
        top_k: int,
        db: Session,
    ) -> list[dict]:
        bm25_k = top_k * settings.BM25_TOP_K_MULTIPLIER

        query_vector = embedding_service.embed_text(query)
        vector_hits = qdrant_service.search(
            query_vector=query_vector,
            tenant_id=tenant_id,
            allowed_classifications=allowed_classifications,
            top_k=bm25_k,
        )

        fts_results = self._fts_search(query, tenant_id, allowed_classifications, bm25_k, db)

        scores: dict[str, float] = {}
        payloads: dict[str, dict] = {}
        vector_scores: dict[str, float] = {}

        for rank, hit in enumerate(vector_hits):
            chunk_id = str(hit.id)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + _rrf_score(rank)
            vector_scores[chunk_id] = hit.score
            if hit.payload:
                payloads[chunk_id] = hit.payload

        for rank, row in enumerate(fts_results):
            chunk_id = str(row["chunk_id"])
            scores[chunk_id] = scores.get(chunk_id, 0.0) + _rrf_score(rank)
            if chunk_id not in payloads:
                payloads[chunk_id] = {
                    "document_id": str(row["document_id"]),
                    "text": row.get("content", ""),
                    "original_filename": row.get("original_filename", ""),
                    "page_number": row.get("page_number"),
                    "chunk_index": row.get("chunk_index", 0),
                    "classification": row.get("classification", "internal"),
                }

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for chunk_id, rrf in ranked:
            results.append(
                {
                    "chunk_id": chunk_id,
                    "score": rrf,
                    "payload": payloads.get(chunk_id, {}),
                    "vector_score": vector_scores.get(chunk_id),
                }
            )
        return results

    def _fts_search(
        self,
        query: str,
        tenant_id: str,
        allowed_classifications: list[str],
        limit: int,
        db: Session,
    ) -> list[dict]:
        sql = text(
            """
            SELECT
                dc.id AS chunk_id,
                dc.document_id,
                dc.text AS content,
                dc.chunk_index,
                dc.page_number,
                d.original_filename,
                d.classification,
                ts_rank_cd(
                    to_tsvector('english', dc.text),
                    plainto_tsquery('english', :query)
                ) AS rank
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE
                d.tenant_id = :tenant_id
                AND d.classification = ANY(:classifications)
                AND to_tsvector('english', dc.text) @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
            """
        )
        rows = db.execute(
            sql,
            {
                "query": query,
                "tenant_id": tenant_id,
                "classifications": allowed_classifications,
                "limit": limit,
            },
        ).fetchall()
        return [dict(r._mapping) for r in rows]


hybrid_retrieval_service = HybridRetrievalService()
