"""Add analyses.voyage_id

Traceability, exactly like prompt_version_id: an analysis records which voyage
fed it, so a report can be traced back to the exploration behind it even after
the person retakes the voyage. Nullable — the voyage is never required, and
every parcours runs identically without one.

batch_alter_table so the file runs on SQLite, which cannot ADD CONSTRAINT.

DOWNGRADE LOSES DATA. Harmless today because nothing populates voyage_id yet,
but once phase 5 does, dropping the column destroys the B2G traceability link
between an analysis and the voyage that fed it.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('analyses') as batch_op:
        batch_op.add_column(sa.Column('voyage_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_analyses_voyage_id', 'voyages', ['voyage_id'], ['id'])
        batch_op.create_index('ix_analyses_voyage_id', ['voyage_id'])


def downgrade():
    with op.batch_alter_table('analyses') as batch_op:
        batch_op.drop_index('ix_analyses_voyage_id')
        batch_op.drop_constraint('fk_analyses_voyage_id', type_='foreignkey')
        batch_op.drop_column('voyage_id')
