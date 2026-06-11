"""Unit tests for reranking service — tested in disabled mode (RERANKING_ENABLED=false)."""
from unittest.mock import MagicMock, patch

from app.services.reranking_service import RerankingService


def _candidates(n: int = 3) -> list[dict]:
    return [
        {"chunk_id": f"c{i}", "score": 1.0 - i * 0.1, "payload": {"text": f"text {i}"}}
        for i in range(n)
    ]


# ── Disabled mode (RERANKING_ENABLED=false) ───────────────────────────────────

def test_disabled_returns_candidates_unchanged():
    svc = RerankingService()
    cands = _candidates(5)
    original_order = [c["chunk_id"] for c in cands]

    import app.services.reranking_service as mod
    mod._cross_encoder = None
    mod._encoder_loaded = False

    with patch("app.services.reranking_service.settings") as s:
        s.RERANKING_ENABLED = False
        result = svc.rerank("query", cands)

    assert [r["chunk_id"] for r in result] == original_order


def test_disabled_returns_same_list_object_or_equivalent():
    svc = RerankingService()
    cands = _candidates(3)

    import app.services.reranking_service as mod
    mod._cross_encoder = None
    mod._encoder_loaded = False

    with patch("app.services.reranking_service.settings") as s:
        s.RERANKING_ENABLED = False
        result = svc.rerank("query", cands)

    assert result is cands  # passthrough returns the same object


def test_empty_candidates_returns_empty():
    svc = RerankingService()
    import app.services.reranking_service as mod
    mod._cross_encoder = None
    mod._encoder_loaded = False

    with patch("app.services.reranking_service.settings") as s:
        s.RERANKING_ENABLED = False
        result = svc.rerank("query", [])

    assert result == []


# ── Enabled mode with mock cross-encoder ─────────────────────────────────────

def test_rerank_sorts_by_cross_encoder_scores():
    svc = RerankingService()
    cands = _candidates(3)
    # We'll have encoder give reversed scores so order should flip
    mock_encoder = MagicMock()
    mock_encoder.predict.return_value = [0.1, 0.5, 0.9]  # chunk2 is best

    import app.services.reranking_service as mod
    mod._cross_encoder = mock_encoder
    mod._encoder_loaded = True

    result = svc.rerank("query", cands)

    # chunk2 (score=0.9) should be first
    assert result[0]["chunk_id"] == "c2"
    assert result[1]["chunk_id"] == "c1"
    assert result[2]["chunk_id"] == "c0"

    # Reset
    mod._cross_encoder = None
    mod._encoder_loaded = False


def test_rerank_attaches_rerank_score():
    svc = RerankingService()
    cands = _candidates(2)
    mock_encoder = MagicMock()
    mock_encoder.predict.return_value = [0.8, 0.3]

    import app.services.reranking_service as mod
    mod._cross_encoder = mock_encoder
    mod._encoder_loaded = True

    result = svc.rerank("query", cands)
    assert "rerank_score" in result[0]

    # Reset
    mod._cross_encoder = None
    mod._encoder_loaded = False


def test_rerank_falls_back_on_encoder_error():
    """If cross-encoder throws, return original order without raising."""
    svc = RerankingService()
    cands = _candidates(3)
    original_order = [c["chunk_id"] for c in cands]
    mock_encoder = MagicMock()
    mock_encoder.predict.side_effect = RuntimeError("GPU OOM")

    import app.services.reranking_service as mod
    mod._cross_encoder = mock_encoder
    mod._encoder_loaded = True

    result = svc.rerank("query", cands)
    assert [r["chunk_id"] for r in result] == original_order

    # Reset
    mod._cross_encoder = None
    mod._encoder_loaded = False
