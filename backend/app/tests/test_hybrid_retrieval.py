"""
Unit tests for hybrid retrieval.

We test the pure RRF merge logic by mocking Qdrant and the embedding service —
no database or network calls needed.
"""
import uuid
from unittest.mock import MagicMock, patch

from app.services.hybrid_retrieval_service import HybridRetrievalService, _rrf_score

# ── RRF score formula ─────────────────────────────────────────────────────────

def test_rrf_score_rank_0():
    # rank=0 → 1/(60+0) = 1/60
    assert abs(_rrf_score(0) - 1 / 60) < 1e-9


def test_rrf_score_rank_10():
    assert abs(_rrf_score(10) - 1 / 70) < 1e-9


def test_rrf_score_decreases_with_rank():
    scores = [_rrf_score(r) for r in range(10)]
    assert scores == sorted(scores, reverse=True)


def test_rrf_score_always_positive():
    for rank in range(100):
        assert _rrf_score(rank) > 0


def test_rrf_score_custom_k():
    assert abs(_rrf_score(0, k=1) - 1.0) < 1e-9
    assert abs(_rrf_score(0, k=100) - 1 / 100) < 1e-9


# ── Merge logic (mock qdrant + embedding + FTS) ───────────────────────────────

def _make_hit(chunk_id: str, score: float, doc_id: str = None) -> MagicMock:
    hit = MagicMock()
    hit.id = chunk_id
    hit.score = score
    hit.payload = {
        "document_id": doc_id or str(uuid.uuid4()),
        "text": f"text for {chunk_id}",
        "original_filename": "test.pdf",
        "page_number": 1,
        "chunk_index": 0,
        "classification": "internal",
    }
    return hit


class TestHybridMerge:
    """Isolates the merge logic without touching the DB."""

    def _make_service(self):
        return HybridRetrievalService()

    def test_vector_only_results_ranked_correctly(self):
        svc = self._make_service()

        hits = [_make_hit(f"chunk-{i}", 0.9 - i * 0.1) for i in range(5)]
        db_mock = MagicMock()

        with (
            patch("app.services.hybrid_retrieval_service.embedding_service.embed_text",
                  return_value=[0.0] * 384),
            patch("app.services.hybrid_retrieval_service.qdrant_service.search",
                  return_value=hits),
        ):
            svc._fts_search = lambda *a, **kw: []
            results = svc.search("test query", "tenant-1", ["internal"], 3, db_mock)

        assert len(results) == 3
        # scores should be descending
        rrf_scores = [r["score"] for r in results]
        assert rrf_scores == sorted(rrf_scores, reverse=True)

    def test_deduplication_across_vector_and_fts(self):
        svc = self._make_service()
        shared_id = "shared-chunk-123"
        hit = _make_hit(shared_id, 0.95)
        fts_row = {
            "chunk_id": shared_id,
            "document_id": str(uuid.uuid4()),
            "content": "shared content",
            "original_filename": "test.pdf",
            "page_number": 1,
            "chunk_index": 0,
            "classification": "internal",
        }
        db_mock = MagicMock()

        with (
            patch("app.services.hybrid_retrieval_service.embedding_service.embed_text",
                  return_value=[0.0] * 384),
            patch("app.services.hybrid_retrieval_service.qdrant_service.search",
                  return_value=[hit]),
        ):
            svc._fts_search = lambda *a, **kw: [fts_row]
            results = svc.search("test query", "tenant-1", ["internal"], 5, db_mock)

        chunk_ids = [r["chunk_id"] for r in results]
        assert chunk_ids.count(shared_id) == 1

    def test_shared_chunk_has_higher_score_than_single_source(self):
        """A chunk appearing in both vector and FTS lists should outscore one appearing in only one."""
        svc = self._make_service()
        shared_id = "shared-chunk"
        vector_only_id = "vector-only"

        shared_hit = _make_hit(shared_id, 0.9)
        vector_hit = _make_hit(vector_only_id, 0.5)
        fts_row = {
            "chunk_id": shared_id,
            "document_id": str(uuid.uuid4()),
            "content": "shared content",
            "original_filename": "test.pdf",
            "page_number": 1,
            "chunk_index": 0,
            "classification": "internal",
        }
        db_mock = MagicMock()

        with (
            patch("app.services.hybrid_retrieval_service.embedding_service.embed_text",
                  return_value=[0.0] * 384),
            patch("app.services.hybrid_retrieval_service.qdrant_service.search",
                  return_value=[shared_hit, vector_hit]),
        ):
            svc._fts_search = lambda *a, **kw: [fts_row]
            results = svc.search("test query", "tenant-1", ["internal"], 5, db_mock)

        result_map = {r["chunk_id"]: r["score"] for r in results}
        assert result_map[shared_id] > result_map[vector_only_id]

    def test_top_k_limits_results(self):
        svc = self._make_service()
        hits = [_make_hit(f"chunk-{i}", 1.0 - i * 0.01) for i in range(20)]
        db_mock = MagicMock()

        with (
            patch("app.services.hybrid_retrieval_service.embedding_service.embed_text",
                  return_value=[0.0] * 384),
            patch("app.services.hybrid_retrieval_service.qdrant_service.search",
                  return_value=hits),
        ):
            svc._fts_search = lambda *a, **kw: []
            results = svc.search("query", "tenant-1", ["internal"], 5, db_mock)

        assert len(results) == 5

    def test_empty_results_returns_empty_list(self):
        svc = self._make_service()
        db_mock = MagicMock()

        with (
            patch("app.services.hybrid_retrieval_service.embedding_service.embed_text",
                  return_value=[0.0] * 384),
            patch("app.services.hybrid_retrieval_service.qdrant_service.search",
                  return_value=[]),
        ):
            svc._fts_search = lambda *a, **kw: []
            results = svc.search("query", "tenant-1", ["internal"], 5, db_mock)

        assert results == []

    def test_result_payload_contains_required_fields(self):
        svc = self._make_service()
        hit = _make_hit("chunk-1", 0.8)
        db_mock = MagicMock()

        with (
            patch("app.services.hybrid_retrieval_service.embedding_service.embed_text",
                  return_value=[0.0] * 384),
            patch("app.services.hybrid_retrieval_service.qdrant_service.search",
                  return_value=[hit]),
        ):
            svc._fts_search = lambda *a, **kw: []
            results = svc.search("query", "tenant-1", ["internal"], 5, db_mock)

        assert len(results) == 1
        r = results[0]
        assert "chunk_id" in r
        assert "score" in r
        assert "payload" in r


# ── Regression: FTS SQL references correct column name ────────────────────────

def test_fts_search_uses_document_chunk_text_column():
    """_fts_search must reference dc.text (not dc.content which doesn't exist)."""
    import inspect

    from app.services.hybrid_retrieval_service import HybridRetrievalService
    src = inspect.getsource(HybridRetrievalService._fts_search)
    assert "dc.content" not in src, (
        "FTS query references dc.content but the column is named dc.text. "
        "Use 'dc.text AS content' instead."
    )
    assert "dc.text" in src
