"""add unlock fields to analyses

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-12 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('analyses', sa.Column('unlock_method', sa.String(length=16), nullable=True))
    op.add_column('analyses', sa.Column('unlocked_at', sa.DateTime(), nullable=True))
    op.add_column('analyses', sa.Column('stripe_session_id', sa.String(length=255), nullable=True))
    op.create_index('ix_analyses_stripe_session_id', 'analyses', ['stripe_session_id'])


def downgrade():
    op.drop_index('ix_analyses_stripe_session_id', table_name='analyses')
    op.drop_column('analyses', 'stripe_session_id')
    op.drop_column('analyses', 'unlocked_at')
    op.drop_column('analyses', 'unlock_method')
