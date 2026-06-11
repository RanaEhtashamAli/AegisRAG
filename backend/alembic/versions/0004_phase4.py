"""Phase 4: security_alerts, tenant_usage_metrics, document_retention_policies

Revision ID: 0004
Revises: 0003
Create Date: 2025-01-01 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_alerts_tenant_id", "security_alerts", ["tenant_id"])
    op.create_index("ix_security_alerts_event_type", "security_alerts", ["event_type"])
    op.create_index("ix_security_alerts_created_at", "security_alerts", ["created_at"])

    op.create_table(
        "tenant_usage_metrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("total_queries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "avg_latency_ms", sa.Float(), nullable=False, server_default="0.0"
        ),
        sa.Column("cache_hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_misses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"
        ),
        sa.Column("model_breakdown_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "period_date", name="uq_usage_tenant_date"),
    )
    op.create_index(
        "ix_tenant_usage_metrics_tenant_id", "tenant_usage_metrics", ["tenant_id"]
    )

    op.create_table(
        "document_retention_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "retention_days", sa.Integer(), nullable=False, server_default="365"
        ),
        sa.Column(
            "auto_delete_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_retention_policy_tenant"),
    )
    op.create_index(
        "ix_document_retention_policies_tenant_id",
        "document_retention_policies",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_table("document_retention_policies")
    op.drop_table("tenant_usage_metrics")
    op.drop_table("security_alerts")
