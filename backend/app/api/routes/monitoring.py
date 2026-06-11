"""Monitoring routes — system health, security alerts, usage metrics, cache stats."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.permissions import require_tenant_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.monitoring import (
    AlertResponse,
    CacheStatsResponse,
    HealthResponse,
    UsageTotalsResponse,
)
from app.services.cache_service import cache_service
from app.services.model_router import model_router
from app.services.security_alert_service import SecurityAlertService
from app.services.usage_metrics_service import UsageMetricsService

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _admin_user(user: User = Depends(require_tenant_admin())):
    return user


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def system_health(
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> HealthResponse:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    cache_stats = cache_service.stats()
    redis_ok = cache_stats.get("available", False)

    qdrant_ok = True
    try:
        from app.services.qdrant_service import qdrant_service
        qdrant_service._get_client().get_collections()
    except Exception:
        qdrant_ok = False

    model_health = await model_router.health()

    return HealthResponse(
        db=db_ok,
        redis=redis_ok,
        qdrant=qdrant_ok,
        ollama=model_health.get("ollama", False),
        vllm=model_health.get("vllm"),
        vllm_enabled=model_health.get("vllm_enabled", False),
    )


# ── Security alerts ───────────────────────────────────────────────────────────


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(
    resolved: bool = False,
    limit: int = 50,
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> list[AlertResponse]:
    alerts = SecurityAlertService(db).list_alerts(
        tenant_id=user.tenant_id, resolved=resolved, limit=limit
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.patch("/alerts/{alert_id}/resolve", response_model=dict)
def resolve_alert(
    alert_id: uuid.UUID,
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    ok = SecurityAlertService(db).resolve(alert_id, user.tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"resolved": True}


# ── Usage metrics ─────────────────────────────────────────────────────────────


@router.get("/usage", response_model=UsageTotalsResponse)
def get_usage(
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> UsageTotalsResponse:
    totals = UsageMetricsService(db).get_totals(user.tenant_id)
    return UsageTotalsResponse(**totals)


@router.get("/usage/history")
def get_usage_history(
    days: int = 30,
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    records = UsageMetricsService(db).get_history(user.tenant_id, days=days)
    return [
        {
            "period_date": r.period_date.isoformat(),
            "total_queries": r.total_queries,
            "total_tokens": r.total_tokens,
            "avg_latency_ms": round(r.avg_latency_ms, 1),
            "cache_hits": r.cache_hits,
            "cache_misses": r.cache_misses,
            "estimated_cost_usd": round(r.estimated_cost_usd, 6),
            "model_breakdown": json.loads(r.model_breakdown_json) if r.model_breakdown_json else {},
        }
        for r in records
    ]


# ── Cache stats ────────────────────────────────────────────────────────────────


@router.get("/cache-stats", response_model=CacheStatsResponse)
def get_cache_stats(
    user: User = Depends(_admin_user),
) -> CacheStatsResponse:
    stats = cache_service.stats()
    return CacheStatsResponse(
        available=stats.get("available", False),
        used_memory_human=stats.get("used_memory_human"),
        connected_clients=stats.get("connected_clients"),
    )
