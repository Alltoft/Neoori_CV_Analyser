"""add progress to analyses

Live percentage for the waiting screen, written from the Anthropic stream while
the analysis runs. Existing rows are finished (or dead) and get 0 — the column
is only read while a row is 'running'.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-24 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'analyses',
        sa.Column('progress', sa.SmallInteger(), nullable=False, server_default='0'),
    )


def downgrade():
    op.drop_column('analyses', 'progress')
