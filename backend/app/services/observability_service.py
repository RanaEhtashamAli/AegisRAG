from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_langfuse: Any = None
_initialized = False


def _get_langfuse() -> Any | None:
    global _langfuse, _initialized
    if _initialized:
        return _langfuse
    _initialized = True
    if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
        return None
    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("Langfuse observability initialized")
    except Exception as exc:
        logger.warning("Langfuse init failed, observability disabled: %s", exc)
        _langfuse = None
    return _langfuse


class SpanContext:
    def __init__(self, trace: Any, name: str, input: Any, metadata: dict | None):
        self._span = None
        if trace is not None:
            try:
                self._span = trace.span(name=name, input=input, metadata=metadata or {})
            except Exception:
                pass

    def end(self, output: Any = None) -> None:
        if self._span:
            try:
                self._span.end(output=output)
            except Exception:
                pass


class TraceContext:
    """Wraps a Langfuse trace. All methods are no-ops if Langfuse is not configured."""

    def __init__(
        self,
        name: str,
        metadata: dict | None = None,
        user_id: str | None = None,
    ):
        self._trace = None
        lf = _get_langfuse()
        if lf is not None:
            try:
                self._trace = lf.trace(
                    name=name, metadata=metadata or {}, user_id=user_id
                )
            except Exception:
                pass

    def span(
        self, name: str, input: Any = None, metadata: dict | None = None
    ) -> SpanContext:
        return SpanContext(self._trace, name, input, metadata)

    def score(self, name: str, value: float) -> None:
        if self._trace:
            try:
                self._trace.score(name=name, value=value)
            except Exception:
                pass

    def update(self, output: Any = None, metadata: dict | None = None) -> None:
        if self._trace:
            try:
                self._trace.update(output=output, metadata=metadata)
            except Exception:
                pass
