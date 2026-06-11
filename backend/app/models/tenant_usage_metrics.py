import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenantUsageMetrics(Base):
    __tablename__ = "tenant_usage_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)  # UTC date of aggregation
    total_queries: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cache_hits: Mapped[int] = mapped_column(Integer, default=0)
    cache_misses: Mapped[int] = mapped_column(Integer, default=0)
    # Estimated cost in USD based on token count + model rates
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    # JSON map: { "model_name": query_count }
    model_breakdown_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
