"""Willingness-to-pay probe after the free report

PM ask (2026-07-29). A hierarchy signal, not a price: people declare more
than they pay, so nothing reads this to set a price.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa


revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'price_feedback',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('analysis_id', sa.String(length=36), nullable=False),
        sa.Column('useful', sa.Boolean(), nullable=True),
        sa.Column('bucket', sa.String(length=24), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'],
                                name='fk_price_feedback_analysis_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # One answer per analysis — re-submitting updates rather than stacking.
        sa.UniqueConstraint('analysis_id', name='uq_price_feedback_analysis_id'),
    )
    op.create_index('ix_price_feedback_analysis_id', 'price_feedback', ['analysis_id'])


def downgrade():
    op.drop_index('ix_price_feedback_analysis_id', table_name='price_feedback')
    op.drop_table('price_feedback')
