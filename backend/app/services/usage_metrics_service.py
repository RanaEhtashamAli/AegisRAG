"""Tenant usage metrics — aggregated daily cost and token tracking."""
from __future__ import annotations

import json
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.tenant_usage_metrics import TenantUsageMetrics


class UsageMetricsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_or_create_today(self, tenant_id: uuid.UUID) -> TenantUsageMetrics:
        today = date.today()
        record = (
            self.db.query(TenantUsageMetrics)
            .filter(
                TenantUsageMetrics.tenant_id == tenant_id,
                TenantUsageMetrics.period_date == today,
            )
            .first()
        )
        if not record:
            record = TenantUsageMetrics(tenant_id=tenant_id, period_date=today)
            self.db.add(record)
            self.db.flush()
        return record

    def record_query(
        self,
        tenant_id: uuid.UUID,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        model: str,
        cache_hit: bool,
        estimated_cost_usd: float,
    ) -> None:
        record = self._get_or_create_today(tenant_id)
        record.total_queries += 1
        record.total_tokens += prompt_tokens + completion_tokens
        # Running average latency
        prev_avg = record.avg_latency_ms
        record.avg_latency_ms = (
            (prev_avg * (record.total_queries - 1) + latency_ms) / record.total_queries
        )
        record.estimated_cost_usd += estimated_cost_usd
        if cache_hit:
            record.cache_hits += 1
        else:
            record.cache_misses += 1

        # Update model breakdown
        breakdown: dict[str, int] = {}
        if record.model_breakdown_json:
            try:
                breakdown = json.loads(record.model_breakdown_json)
            except Exception:
                pass
        breakdown[model] = breakdown.get(model, 0) + 1
        record.model_breakdown_json = json.dumps(breakdown)

        self.db.commit()

    def get_history(
        self, tenant_id: uuid.UUID, days: int = 30
    ) -> list[TenantUsageMetrics]:
        from datetime import timedelta
        since = date.today() - timedelta(days=days)
        return (
            self.db.query(TenantUsageMetrics)
            .filter(
                TenantUsageMetrics.tenant_id == tenant_id,
                TenantUsageMetrics.period_date >= since,
            )
            .order_by(TenantUsageMetrics.period_date.asc())
            .all()
        )

    def get_totals(self, tenant_id: uuid.UUID) -> dict:
        from sqlalchemy import func
        row = (
            self.db.query(
                func.sum(TenantUsageMetrics.total_queries).label("queries"),
                func.sum(TenantUsageMetrics.total_tokens).label("tokens"),
                func.sum(TenantUsageMetrics.estimated_cost_usd).label("cost"),
                func.sum(TenantUsageMetrics.cache_hits).label("hits"),
                func.sum(TenantUsageMetrics.cache_misses).label("misses"),
            )
            .filter(TenantUsageMetrics.tenant_id == tenant_id)
            .first()
        )
        return {
            "total_queries": row.queries or 0,
            "total_tokens": row.tokens or 0,
            "estimated_cost_usd": round(float(row.cost or 0), 6),
            "cache_hits": row.hits or 0,
            "cache_misses": row.misses or 0,
        }
