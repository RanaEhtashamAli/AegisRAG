import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentRetentionPolicy(Base):
    __tablename__ = "document_retention_policies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, unique=True, index=True
    )
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    auto_delete_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
