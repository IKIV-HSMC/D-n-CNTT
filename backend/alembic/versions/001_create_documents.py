"""create documents table

Revision ID: 001
Revises:
Create Date: 2026-10-10 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('subject_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('stored_filename', sa.String(255), nullable=False, unique=True),
        sa.Column('file_type', sa.String(10), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('uploaded', 'extracting', 'extracted', 'failed', name='documentstatus'),
            nullable=False,
            server_default='uploaded',
        ),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_file_type', 'documents', ['file_type'])
    op.create_index('ix_documents_created_at', 'documents', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_documents_created_at', table_name='documents')
    op.drop_index('ix_documents_file_type', table_name='documents')
    op.drop_index('ix_documents_status', table_name='documents')
    op.drop_table('documents')
    op.execute("DROP TYPE IF EXISTS documentstatus")
