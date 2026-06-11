import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings

_SYSTEM_PROMPT = (
    "You are AegisRAG, a secure enterprise assistant. "
    "Answer only using the provided context. "
    "If the context does not contain enough information, say you do not have enough information. "
    "Do not invent facts."
)


class LLMService:
    def generate_answer(
        self,
        question: str,
        context_chunks: list[str],
        history_prefix: str = "",
    ) -> str:
        numbered_context = "\n\n".join(
            f"[{i + 1}] {chunk}" for i, chunk in enumerate(context_chunks)
        )
        parts = []
        if history_prefix:
            parts.append(f"Previous conversation:\n{history_prefix}\n")
        parts.append(f"Context:\n{numbered_context}\n\nQuestion: {question}")
        user_prompt = "\n".join(parts)

        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": user_prompt,
            "system": _SYSTEM_PROMPT,
            "stream": False,
        }

        with httpx.Client(timeout=120.0) as client:
            response = client.post(f"{settings.OLLAMA_BASE_URL}/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "").strip()

    async def generate_answer_stream(
        self,
        question: str,
        context_chunks: list[str],
        history_prefix: str = "",
    ) -> AsyncIterator[str]:
        """Yield answer tokens one by one via Ollama streaming API."""
        numbered_context = "\n\n".join(
            f"[{i + 1}] {chunk}" for i, chunk in enumerate(context_chunks)
        )
        parts = []
        if history_prefix:
            parts.append(f"Previous conversation:\n{history_prefix}\n")
        parts.append(f"Context:\n{numbered_context}\n\nQuestion: {question}")
        user_prompt = "\n".join(parts)

        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": user_prompt,
            "system": _SYSTEM_PROMPT,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST", f"{settings.OLLAMA_BASE_URL}/api/generate", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except Exception:
                        continue


llm_service = LLMService()
