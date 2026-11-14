"""add persistent flashcards and SM-2 review progress

Revision ID: 004
Revises: 003
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flashcards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_key", sa.String(length=64), nullable=False),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("node_id", sa.String(length=80), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "card_key", name="uq_flashcard_document_key"),
    )
    op.create_index("ix_flashcards_document_id", "flashcards", ["document_id"])

    op.create_table(
        "flashcard_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flashcard_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repetitions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("interval_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ease_factor", sa.Float(), server_default="2.5", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_reviews", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lapses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flashcard_id"], ["flashcards.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "flashcard_id", name="uq_flashcard_progress_user_card"),
        sa.CheckConstraint("repetitions >= 0", name="ck_flashcard_progress_repetitions"),
        sa.CheckConstraint("interval_days >= 0", name="ck_flashcard_progress_interval"),
        sa.CheckConstraint("ease_factor >= 1.3", name="ck_flashcard_progress_ease"),
    )
    op.create_index("ix_flashcard_progress_user_id", "flashcard_progress", ["user_id"])
    op.create_index("ix_flashcard_progress_flashcard_id", "flashcard_progress", ["flashcard_id"])
    op.create_index("ix_flashcard_progress_due_at", "flashcard_progress", ["due_at"])

    op.create_table(
        "review_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flashcard_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.String(length=8), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_before_days", sa.Integer(), nullable=False),
        sa.Column("interval_after_days", sa.Integer(), nullable=False),
        sa.Column("ease_before", sa.Float(), nullable=False),
        sa.Column("ease_after", sa.Float(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flashcard_id"], ["flashcards.id"], ondelete="CASCADE"),
        sa.CheckConstraint("rating IN ('again', 'hard', 'good', 'easy')", name="ck_review_event_rating"),
    )
    op.create_index("ix_review_events_user_id", "review_events", ["user_id"])
    op.create_index("ix_review_events_flashcard_id", "review_events", ["flashcard_id"])


def downgrade() -> None:
    op.drop_index("ix_review_events_flashcard_id", table_name="review_events")
    op.drop_index("ix_review_events_user_id", table_name="review_events")
    op.drop_table("review_events")
    op.drop_index("ix_flashcard_progress_due_at", table_name="flashcard_progress")
    op.drop_index("ix_flashcard_progress_flashcard_id", table_name="flashcard_progress")
    op.drop_index("ix_flashcard_progress_user_id", table_name="flashcard_progress")
    op.drop_table("flashcard_progress")
    op.drop_index("ix_flashcards_document_id", table_name="flashcards")
    op.drop_table("flashcards")
