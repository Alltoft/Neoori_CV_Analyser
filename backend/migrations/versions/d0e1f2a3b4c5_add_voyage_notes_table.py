"""Create the voyage_notes table

A counselor's private note on one voyage. Plaintext on purpose: it is the
counselor's own writing about their own practice, not the person's answers —
the same call counselor_notes makes for analyses.

One note per (voyage, counselor) pair, and the FK cascades so erasing a voyage
erases the notes written on it.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'voyage_notes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('voyage_id', sa.String(length=36), nullable=False),
        sa.Column('counselor_id', sa.String(length=36), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['voyage_id'], ['voyages.id'],
                                name='fk_voyage_notes_voyage_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['counselor_id'], ['users.id'],
                                name='fk_voyage_notes_counselor_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('voyage_id', 'counselor_id',
                            name='uq_voyage_notes_voyage_counselor'),
    )
    op.create_index('ix_voyage_notes_voyage_id', 'voyage_notes', ['voyage_id'])


def downgrade():
    op.drop_index('ix_voyage_notes_voyage_id', table_name='voyage_notes')
    op.drop_table('voyage_notes')
