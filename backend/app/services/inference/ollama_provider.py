from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import logger
from app.services.inference.base_provider import (
    BaseInferenceProvider,
    InferenceRequest,
    InferenceResponse,
)


class OllamaProvider(BaseInferenceProvider):
    provider_name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self._base_url = base_url or settings.OLLAMA_BASE_URL
        self._model = model or settings.OLLAMA_MODEL

    def default_model(self) -> str:
        return self._model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        model = request.model or self._model
        payload = {
            "model": model,
            "prompt": request.prompt,
            "system": request.system_prompt,
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_BASE_URL and 120.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/generate",
                    json=payload,
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("ollama_generate_error", model=model, error=str(exc))
            raise

        latency_ms = int((time.monotonic() - start) * 1000)
        content = data.get("response", "").strip()
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return InferenceResponse(
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            provider=self.provider_name,
        )

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[str]:
        model = request.model or self._model
        payload = {
            "model": model,
            "prompt": request.prompt,
            "system": request.system_prompt,
            "stream": True,
            "options": {"temperature": request.temperature},
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST", f"{self._base_url}/api/generate", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
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

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
