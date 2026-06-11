"""Phase 3: chat sessions, evaluation runs, prompt security events

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-01 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default="New Chat"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_sessions_tenant_id", "chat_sessions", ["tenant_id"])
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("retrieved_doc_ids", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("run_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "completed_questions", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("faithfulness", sa.Float(), nullable=True),
        sa.Column("answer_relevancy", sa.Float(), nullable=True),
        sa.Column("context_recall", sa.Float(), nullable=True),
        sa.Column("context_precision", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("results_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "prompt_security_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("detection_type", sa.String(100), nullable=False),
        sa.Column("matched_pattern", sa.String(500), nullable=True),
        sa.Column(
            "risk_level", sa.String(20), nullable=False, server_default="medium"
        ),
        sa.Column(
            "action_taken", sa.String(50), nullable=False, server_default="blocked"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prompt_security_events_tenant_id",
        "prompt_security_events",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_table("prompt_security_events")
    op.drop_table("evaluation_runs")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
