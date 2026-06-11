from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    db: bool
    redis: bool
    qdrant: bool
    ollama: bool
    vllm: bool | None
    vllm_enabled: bool


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    severity: str
    event_type: str
    description: str
    resolved: bool
    resolved_at: datetime | None
    created_at: datetime


class UsageTotalsResponse(BaseModel):
    total_queries: int
    total_tokens: int
    estimated_cost_usd: float
    cache_hits: int
    cache_misses: int


class CacheStatsResponse(BaseModel):
    available: bool
    used_memory_human: str | None = None
    connected_clients: int | None = None
