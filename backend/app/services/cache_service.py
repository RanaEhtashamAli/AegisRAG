"""Redis-backed caching for embeddings, retrieval results, and RAG responses.

Cache key structure:
  aegis:{tenant_id}:embed:{text_hash}
  aegis:{tenant_id}:{cls_hash}:{query_hash}:retrieve
  aegis:{tenant_id}:{cls_hash}:{query_hash}:response

Any query scope that includes the restricted classification bypasses retrieval
and response caching to prevent cross-context leakage.
"""
from __future__ import annotations

import hashlib
import json
import logging

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "aegis"
_RESTRICTED = "restricted"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _classifications_hash(classifications: list[str]) -> str:
    return _sha256(",".join(sorted(classifications)))


class CacheService:
    """Singleton Redis cache. All methods are no-ops if CACHE_ENABLED=false."""

    _client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis | None:
        if not settings.CACHE_ENABLED:
            return None
        if self._client is None:
            try:
                self._client = redis.from_url(
                    settings.REDIS_URL, decode_responses=True, socket_timeout=1.0
                )
                self._client.ping()
            except Exception as exc:
                logger.warning("cache_unavailable: %s", exc)
                self._client = None
        return self._client

    # ── Embedding cache ──────────────────────────────────────────────────────

    def get_embedding(self, text: str) -> list[float] | None:
        r = self._get_client()
        if not r:
            return None
        try:
            key = f"{_PREFIX}:embed:{_sha256(text)}"
            raw = r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def set_embedding(self, text: str, vector: list[float]) -> None:
        r = self._get_client()
        if not r:
            return
        try:
            key = f"{_PREFIX}:embed:{_sha256(text)}"
            r.setex(key, settings.EMBEDDING_CACHE_TTL, json.dumps(vector))
        except Exception:
            pass

    # ── Retrieval cache ───────────────────────────────────────────────────────

    def _retrieval_key(
        self, tenant_id: str, query: str, classifications: list[str]
    ) -> str:
        return (
            f"{_PREFIX}:{tenant_id}:{_classifications_hash(classifications)}"
            f":{_sha256(query)}:retrieve"
        )

    def _contains_restricted(self, classifications: list[str]) -> bool:
        return _RESTRICTED in set(classifications)

    def get_retrieval(
        self, tenant_id: str, query: str, classifications: list[str]
    ) -> list[dict] | None:
        if self._contains_restricted(classifications):
            return None
        r = self._get_client()
        if not r:
            return None
        try:
            raw = r.get(self._retrieval_key(tenant_id, query, classifications))
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def set_retrieval(
        self,
        tenant_id: str,
        query: str,
        classifications: list[str],
        results: list[dict],
    ) -> None:
        if self._contains_restricted(classifications):
            return
        r = self._get_client()
        if not r:
            return
        try:
            r.setex(
                self._retrieval_key(tenant_id, query, classifications),
                settings.RETRIEVAL_CACHE_TTL,
                json.dumps(results),
            )
        except Exception:
            pass

    # ── Response cache ────────────────────────────────────────────────────────

    def _response_key(
        self, tenant_id: str, query: str, classifications: list[str]
    ) -> str:
        return (
            f"{_PREFIX}:{tenant_id}:{_classifications_hash(classifications)}"
            f":{_sha256(query)}:response"
        )

    def get_response(
        self, tenant_id: str, query: str, classifications: list[str]
    ) -> str | None:
        if self._contains_restricted(classifications):
            return None
        r = self._get_client()
        if not r:
            return None
        try:
            return r.get(self._response_key(tenant_id, query, classifications))
        except Exception:
            return None

    def set_response(
        self,
        tenant_id: str,
        query: str,
        classifications: list[str],
        answer: str,
    ) -> None:
        if self._contains_restricted(classifications):
            return
        r = self._get_client()
        if not r:
            return
        try:
            r.setex(
                self._response_key(tenant_id, query, classifications),
                settings.RESPONSE_CACHE_TTL,
                answer,
            )
        except Exception:
            pass

    # ── Invalidation ─────────────────────────────────────────────────────────

    def invalidate_tenant(self, tenant_id: str) -> int:
        """Delete all cache keys for a tenant. Returns key count deleted."""
        r = self._get_client()
        if not r:
            return 0
        try:
            keys = list(r.scan_iter(f"{_PREFIX}:{tenant_id}:*"))
            if keys:
                return r.delete(*keys)
            return 0
        except Exception:
            return 0

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        r = self._get_client()
        if not r:
            return {"available": False}
        try:
            info = r.info("memory")
            return {
                "available": True,
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": r.info("clients").get("connected_clients"),
            }
        except Exception:
            return {"available": False}


cache_service = CacheService()
