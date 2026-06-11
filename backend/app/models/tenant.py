import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    users = relationship("User", back_populates="tenant")
    documents = relationship("Document", back_populates="tenant")
    document_chunks = relationship("DocumentChunk", back_populates="tenant")
    audit_events = relationship("AuditEvent", back_populates="tenant")
