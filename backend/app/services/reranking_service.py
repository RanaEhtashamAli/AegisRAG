from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_cross_encoder = None
_encoder_loaded = False


def _get_cross_encoder():
    global _cross_encoder, _encoder_loaded
    if _encoder_loaded:
        return _cross_encoder
    _encoder_loaded = True
    if not settings.RERANKING_ENABLED:
        return None
    try:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(settings.RERANKING_MODEL)
        logger.info("Cross-encoder reranker loaded: %s", settings.RERANKING_MODEL)
    except Exception as exc:
        logger.warning("Cross-encoder load failed, reranking disabled: %s", exc)
        _cross_encoder = None
    return _cross_encoder


class RerankingService:
    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """Rerank candidates using cross-encoder. Falls back to original order."""
        encoder = _get_cross_encoder()
        if not encoder or not candidates:
            return candidates

        try:
            pairs = [(query, c["payload"].get("text", "")[:512]) for c in candidates]
            scores = encoder.predict(pairs)
            ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
            for item, score in ranked:
                item["rerank_score"] = float(score)
            return [item for item, _ in ranked]
        except Exception as exc:
            logger.warning("Reranking failed, using original order: %s", exc)
            return candidates


reranking_service = RerankingService()
