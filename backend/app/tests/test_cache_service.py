"""Unit tests for CacheService — Redis is mocked throughout."""
import json
from unittest.mock import MagicMock, patch

from app.services.cache_service import CacheService, _classifications_hash, _sha256

# ── Hash helpers ──────────────────────────────────────────────────────────────

def test_sha256_is_deterministic():
    assert _sha256("hello") == _sha256("hello")


def test_sha256_different_inputs_different_hashes():
    assert _sha256("hello") != _sha256("world")


def test_sha256_length_is_16():
    assert len(_sha256("anything")) == 16


def test_classifications_hash_order_independent():
    assert _classifications_hash(["public", "internal"]) == \
           _classifications_hash(["internal", "public"])


def test_classifications_hash_different_sets_differ():
    assert _classifications_hash(["public"]) != _classifications_hash(["restricted"])


# ── Cache disabled ────────────────────────────────────────────────────────────

def test_all_get_methods_return_none_when_disabled():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = False
        assert svc.get_embedding("text") is None
        assert svc.get_retrieval("t1", "q", ["public"]) is None
        assert svc.get_response("t1", "q", ["public"]) is None


def test_set_methods_are_noop_when_disabled():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = False
        svc.set_embedding("text", [0.1, 0.2])  # should not raise
        svc.set_retrieval("t1", "q", ["public"], [])
        svc.set_response("t1", "q", ["public"], "answer")


# ── Restricted classification bypass ─────────────────────────────────────────

def test_get_retrieval_returns_none_for_restricted_only():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        svc._client = mock_redis
        result = svc.get_retrieval("tenant", "query", ["restricted"])
    assert result is None
    mock_redis.get.assert_not_called()


def test_set_retrieval_skips_restricted_only():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        svc._client = mock_redis
        svc.set_retrieval("tenant", "query", ["restricted"], [{"chunk": "data"}])
    mock_redis.setex.assert_not_called()


def test_get_response_returns_none_for_restricted_only():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        svc._client = mock_redis
        result = svc.get_response("tenant", "query", ["restricted"])
    assert result is None


# ── Mixed classifications containing restricted ───────────────────────────────

_MIXED = ["public", "internal", "confidential", "restricted"]


def test_get_retrieval_returns_none_when_restricted_is_in_mixed_classifications():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        svc._client = mock_redis
        result = svc.get_retrieval("tenant", "query", _MIXED)
    assert result is None
    mock_redis.get.assert_not_called()


def test_set_retrieval_skips_when_restricted_is_in_mixed_classifications():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        svc._client = mock_redis
        svc.set_retrieval("tenant", "query", _MIXED, [{"chunk": "data"}])
    mock_redis.setex.assert_not_called()


def test_get_response_returns_none_when_restricted_is_in_mixed_classifications():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        svc._client = mock_redis
        result = svc.get_response("tenant", "query", _MIXED)
    assert result is None
    mock_redis.get.assert_not_called()


def test_set_response_skips_when_restricted_is_in_mixed_classifications():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        s.RESPONSE_CACHE_TTL = 60
        mock_redis = MagicMock()
        svc._client = mock_redis
        svc.set_response("tenant", "query", _MIXED, "some answer")
    mock_redis.setex.assert_not_called()


# ── Cache hit / miss ──────────────────────────────────────────────────────────

def test_get_retrieval_returns_cached_data():
    svc = CacheService()
    cached = [{"chunk_id": "abc", "score": 0.9}]

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached)
        svc._client = mock_redis

        result = svc.get_retrieval("tenant", "query", ["public"])

    assert result == cached


def test_get_retrieval_returns_none_on_cache_miss():
    svc = CacheService()

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        svc._client = mock_redis

        result = svc.get_retrieval("tenant", "query", ["public"])

    assert result is None


def test_set_retrieval_calls_setex_with_correct_ttl():
    svc = CacheService()
    data = [{"chunk_id": "xyz"}]

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        s.RETRIEVAL_CACHE_TTL = 300
        mock_redis = MagicMock()
        svc._client = mock_redis

        svc.set_retrieval("tenant", "query", ["public"], data)

    mock_redis.setex.assert_called_once()
    _key, ttl, _value = mock_redis.setex.call_args[0]
    assert ttl == 300


def test_get_response_returns_cached_answer():
    svc = CacheService()

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        mock_redis.get.return_value = "The answer is 42."
        svc._client = mock_redis

        result = svc.get_response("tenant", "question", ["public"])

    assert result == "The answer is 42."


def test_set_response_calls_setex():
    svc = CacheService()

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        s.RESPONSE_CACHE_TTL = 60
        mock_redis = MagicMock()
        svc._client = mock_redis

        svc.set_response("tenant", "question", ["public"], "answer text")

    mock_redis.setex.assert_called_once()


# ── Embedding cache ───────────────────────────────────────────────────────────

def test_get_embedding_returns_vector():
    svc = CacheService()
    vector = [0.1, 0.2, 0.3]

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(vector)
        svc._client = mock_redis

        result = svc.get_embedding("some text")

    assert result == vector


def test_get_embedding_returns_none_on_miss():
    svc = CacheService()

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        svc._client = mock_redis

        result = svc.get_embedding("missing text")

    assert result is None


# ── Invalidation ──────────────────────────────────────────────────────────────

def test_invalidate_tenant_deletes_keys():
    svc = CacheService()

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = ["aegis:t1:key1", "aegis:t1:key2"]
        mock_redis.delete.return_value = 2
        svc._client = mock_redis

        count = svc.invalidate_tenant("t1")

    assert count == 2
    mock_redis.delete.assert_called_once()


def test_invalidate_tenant_returns_zero_when_disabled():
    svc = CacheService()

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = False
        count = svc.invalidate_tenant("t1")

    assert count == 0


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_stats_returns_unavailable_when_disabled():
    svc = CacheService()
    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = False
        stats = svc.stats()
    assert stats["available"] is False


def test_stats_returns_memory_info():
    svc = CacheService()

    with patch("app.services.cache_service.settings") as s:
        s.CACHE_ENABLED = True
        mock_redis = MagicMock()
        mock_redis.info.side_effect = lambda section: (
            {"used_memory_human": "1.5M"} if section == "memory"
            else {"connected_clients": 3}
        )
        svc._client = mock_redis

        stats = svc.stats()

    assert stats["available"] is True
    assert stats["used_memory_human"] == "1.5M"
    assert stats["connected_clients"] == 3
