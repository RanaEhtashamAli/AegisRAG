import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    # status: uploaded | processing | indexed | failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # classification: public | internal | confidential | restricted
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="documents")
    uploaded_by = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    pii_findings = relationship("PiiFinding", back_populates="document", cascade="all, delete-orphan")
