import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PiiFinding(Base):
    __tablename__ = "pii_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Qdrant point ID of the chunk where PII was found (null if scanned at page level)
    chunk_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pii_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # SHA-256 of the raw matched text — raw value is never stored
    matched_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Masked version safe to display: jo***@example.com, **** **** **** 1234
    matched_text_preview: Mapped[str] = mapped_column(String(128), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    tenant = relationship("Tenant")
    document = relationship("Document", back_populates="pii_findings")
