import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending/running/completed/failed
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    completed_questions: Mapped[int] = mapped_column(Integer, default=0)
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_relevancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    results_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
