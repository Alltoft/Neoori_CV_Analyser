"""add path column to prompt_versions

Revision ID: a1b2c3d4e5f6
Revises: 7ac94ad5a1c9
Create Date: 2026-06-04

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '7ac94ad5a1c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'prompt_versions',
        sa.Column('path', sa.String(length=1), nullable=False, server_default='A'),
    )
    op.create_index('ix_prompt_versions_path_active', 'prompt_versions', ['path', 'is_active'])


def downgrade():
    op.drop_index('ix_prompt_versions_path_active', table_name='prompt_versions')
    op.drop_column('prompt_versions', 'path')
