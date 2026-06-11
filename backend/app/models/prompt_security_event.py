import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PromptSecurityEvent(Base):
    __tablename__ = "prompt_security_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    detection_type: Mapped[str] = mapped_column(String(100), nullable=False)
    matched_pattern: Mapped[str | None] = mapped_column(String(500), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")  # low/medium/high
    action_taken: Mapped[str] = mapped_column(String(50), default="blocked")  # blocked/flagged
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
