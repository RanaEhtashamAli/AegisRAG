"""Phase 2: RBAC, document classification, invitations, PII findings, audit enhancements

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-02 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users: add role column ---
    op.add_column(
        "users",
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
    )

    # --- documents: add classification column ---
    op.add_column(
        "documents",
        sa.Column(
            "classification",
            sa.String(32),
            nullable=False,
            server_default="internal",
        ),
    )
    op.create_index("ix_documents_classification", "documents", ["classification"])

    # --- audit_events: add request context columns ---
    op.add_column("audit_events", sa.Column("ip_address", sa.String(45), nullable=True))
    op.add_column("audit_events", sa.Column("user_agent", sa.String(512), nullable=True))

    # --- tenant_invitations table ---
    op.create_table(
        "tenant_invitations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column(
            "invited_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tenant_invitations_tenant_id", "tenant_invitations", ["tenant_id"])
    op.create_index("ix_tenant_invitations_email", "tenant_invitations", ["email"])
    op.create_index("ix_tenant_invitations_token_hash", "tenant_invitations", ["token_hash"])

    # --- pii_findings table ---
    op.create_table(
        "pii_findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_id", sa.String(64), nullable=True),
        sa.Column("pii_type", sa.String(64), nullable=False),
        sa.Column("matched_text_hash", sa.String(64), nullable=False),
        sa.Column("matched_text_preview", sa.String(128), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_pii_findings_tenant_id", "pii_findings", ["tenant_id"])
    op.create_index("ix_pii_findings_document_id", "pii_findings", ["document_id"])


def downgrade() -> None:
    op.drop_table("pii_findings")
    op.drop_table("tenant_invitations")
    op.drop_column("audit_events", "user_agent")
    op.drop_column("audit_events", "ip_address")
    op.drop_index("ix_documents_classification", table_name="documents")
    op.drop_column("documents", "classification")
    op.drop_column("users", "role")
