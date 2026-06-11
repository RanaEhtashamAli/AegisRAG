"""Model routing — selects the right inference provider and model for a given request.

Routing criteria:
  - VLLM_ENABLED=false → always use Ollama
  - prompt token count > COMPLEX_QUERY_TOKEN_THRESHOLD → strong model
  - classification == "restricted" → local-only model (Ollama, never vLLM cloud)
  - otherwise → lightweight/fast model via vLLM if available
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.services.inference.base_provider import BaseInferenceProvider, InferenceRequest
from app.services.inference.ollama_provider import OllamaProvider
from app.services.inference.vllm_provider import VLLMProvider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are AegisRAG, a secure enterprise assistant. "
    "Answer only using the provided context. "
    "If the context does not contain enough information, say you do not have enough information. "
    "Do not invent facts."
)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


class ModelRouter:
    """Selects an inference provider and constructs InferenceRequest objects."""

    def __init__(self) -> None:
        self._ollama = OllamaProvider()
        self._vllm = VLLMProvider() if settings.VLLM_ENABLED else None

    def _select_provider(
        self,
        prompt: str,
        classification: str | None = None,
    ) -> tuple[BaseInferenceProvider, str]:
        """Return (provider, model_name) for a given prompt + classification."""

        # Restricted docs must never leave local inference
        if classification == "restricted":
            return self._ollama, settings.OLLAMA_MODEL

        if self._vllm is None:
            return self._ollama, settings.OLLAMA_MODEL

        token_count = _estimate_tokens(prompt)
        if token_count > settings.COMPLEX_QUERY_TOKEN_THRESHOLD:
            # Complex query → stronger vLLM model
            logger.debug(
                "model_router_complex",
                tokens=token_count,
                threshold=settings.COMPLEX_QUERY_TOKEN_THRESHOLD,
            )
            return self._vllm, settings.VLLM_MODEL

        # Default: lightweight vLLM model for speed
        return self._vllm, settings.VLLM_MODEL

    def build_request(
        self,
        question: str,
        context_chunks: list[str],
        history_prefix: str = "",
        classification: str | None = None,
    ) -> tuple[BaseInferenceProvider, InferenceRequest]:
        numbered_context = "\n\n".join(
            f"[{i + 1}] {chunk}" for i, chunk in enumerate(context_chunks)
        )
        parts: list[str] = []
        if history_prefix:
            parts.append(f"Previous conversation:\n{history_prefix}\n")
        parts.append(f"Context:\n{numbered_context}\n\nQuestion: {question}")
        full_prompt = "\n".join(parts)

        provider, model = self._select_provider(full_prompt, classification)

        request = InferenceRequest(
            prompt=full_prompt,
            system_prompt=_SYSTEM_PROMPT,
            model=model,
            temperature=0.1,
            max_tokens=1024,
            metadata={
                "classification": classification,
                "estimated_tokens": _estimate_tokens(full_prompt),
            },
        )
        return provider, request

    async def health(self) -> dict:
        ollama_ok = await self._ollama.health_check()
        vllm_ok = (await self._vllm.health_check()) if self._vllm else None
        return {
            "ollama": ollama_ok,
            "vllm": vllm_ok,
            "vllm_enabled": settings.VLLM_ENABLED,
        }


model_router = ModelRouter()
