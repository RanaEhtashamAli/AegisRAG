"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-02 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("ix_documents_uploaded_by_id", "documents", ["uploaded_by_id"])

    op.create_table(
        "document_chunks",
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
        sa.Column("qdrant_point_id", sa.String(64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_document_chunks_tenant_id", "document_chunks", ["tenant_id"])
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(128), nullable=True),
        sa.Column("entity_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("tenants")
