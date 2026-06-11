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

# vLLM exposes an OpenAI-compatible API
_CHAT_ENDPOINT = "/v1/chat/completions"
_HEALTH_ENDPOINT = "/health"


class VLLMProvider(BaseInferenceProvider):
    """vLLM inference provider using the OpenAI-compatible chat completions API."""

    provider_name = "vllm"

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self._base_url = (base_url or settings.VLLM_BASE_URL).rstrip("/")
        self._model = model or settings.VLLM_MODEL

    def default_model(self) -> str:
        return self._model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        model = request.model or self._model
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=float(settings.VLLM_TIMEOUT)) as client:
                resp = await client.post(
                    f"{self._base_url}{_CHAT_ENDPOINT}", json=payload
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("vllm_generate_error", model=model, error=str(exc))
            raise

        latency_ms = int((time.monotonic() - start) * 1000)
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return InferenceResponse(
            content=choice.strip(),
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency_ms,
            provider=self.provider_name,
        )

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[str]:
        model = request.model or self._model
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=float(settings.VLLM_TIMEOUT)) as client:
            async with client.stream(
                "POST", f"{self._base_url}{_CHAT_ENDPOINT}", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                        delta = data["choices"][0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        continue

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}{_HEALTH_ENDPOINT}")
                return resp.status_code == 200
        except Exception:
            return False
