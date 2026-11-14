"""add persistent AI processing runs

Revision ID: 005
Revises: 004
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processing_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("stage", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("worker_id", sa.String(length=80), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("mode IN ('engine', 'ai')", name="ck_processing_run_mode"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="ck_processing_run_status",
        ),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_processing_run_progress"),
        sa.CheckConstraint("attempts >= 0", name="ck_processing_run_attempts"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_processing_run_max_attempts"),
    )
    op.create_index("ix_processing_runs_document_id", "processing_runs", ["document_id"])
    op.create_index("ix_processing_runs_user_id", "processing_runs", ["user_id"])
    op.create_index("ix_processing_runs_status", "processing_runs", ["status"])
    op.create_index("ix_processing_runs_lease_expires_at", "processing_runs", ["lease_expires_at"])
    op.create_index("ix_processing_runs_retry_after", "processing_runs", ["retry_after"])
    op.create_index("ix_processing_runs_created_at", "processing_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_processing_runs_retry_after", table_name="processing_runs")
    op.drop_index("ix_processing_runs_created_at", table_name="processing_runs")
    op.drop_index("ix_processing_runs_lease_expires_at", table_name="processing_runs")
    op.drop_index("ix_processing_runs_status", table_name="processing_runs")
    op.drop_index("ix_processing_runs_user_id", table_name="processing_runs")
    op.drop_index("ix_processing_runs_document_id", table_name="processing_runs")
    op.drop_table("processing_runs")
