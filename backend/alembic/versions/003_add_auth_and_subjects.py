"""add users, sessions, subjects and ownership constraints

Revision ID: 003
Revises: 002
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_subject_owner_name"),
    )
    op.create_index("ix_subjects_owner_user_id", "subjects", ["owner_user_id"])

    # Older anonymous uploads cannot safely be assigned to a new account.
    # Clear unresolvable references before adding the ownership foreign keys.
    op.execute("UPDATE documents SET user_id = NULL WHERE user_id IS NOT NULL")
    op.execute("UPDATE documents SET subject_id = NULL WHERE subject_id IS NOT NULL")
    op.create_foreign_key(
        "fk_documents_user_id_users", "documents", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_documents_subject_id_subjects", "documents", "subjects", ["subject_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_index("ix_documents_subject_id", "documents", ["subject_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_subject_id", table_name="documents")
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_constraint("fk_documents_subject_id_subjects", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_user_id_users", "documents", type_="foreignkey")
    op.drop_index("ix_subjects_owner_user_id", table_name="subjects")
    op.drop_table("subjects")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("users")
