from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class InferenceRequest:
    prompt: str
    system_prompt: str = ""
    model: str = ""
    temperature: float = 0.1
    max_tokens: int = 1024
    stream: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class InferenceResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    provider: str = ""

    @property
    def estimated_cost_usd(self) -> float:
        """Rough cost estimate — override per provider with real rates."""
        return self.total_tokens * 0.000002  # $2 / 1M tokens placeholder


class BaseInferenceProvider(ABC):
    """Abstract base for inference backends (Ollama, vLLM, etc.)."""

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    async def generate(self, request: InferenceRequest) -> InferenceResponse: ...

    @abstractmethod
    async def generate_stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[str]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def default_model(self) -> str: ...
