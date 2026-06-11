import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TenantInvitation(Base):
    __tablename__ = "tenant_invitations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    # SHA-256 of the raw invite token — raw token is never persisted
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # pending | accepted | revoked | expired
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant")
    invited_by = relationship("User", foreign_keys=[invited_by_id])
