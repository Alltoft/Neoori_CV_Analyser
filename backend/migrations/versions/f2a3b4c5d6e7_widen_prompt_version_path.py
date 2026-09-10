"""Widen prompt_versions.path from String(1) to String(16)

PromptVersion.path stops being a parcours id and becomes a prompt *slot*:
'1' | '2' | '3' | 'voyage_micro' | 'voyage_portrait' (services/prompt_slots.py).
Using '4'/'5' for the two voyage prompts would make them show up as parcours
everywhere the section registry is iterated. 'voyage_portrait' is 15 characters,
so 16 is the exact fit.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prompt_versions') as batch_op:
        batch_op.alter_column(
            'path',
            existing_type=sa.String(length=1),
            type_=sa.String(length=16),
            existing_nullable=False,
            existing_server_default='1',
        )


def downgrade():
    # Narrowing first would truncate or fail outright on MySQL: fold the two
    # voyage slots back onto parcours 1 before the column can hold one char.
    op.execute("UPDATE prompt_versions SET path = '1' WHERE LENGTH(path) > 1")
    with op.batch_alter_table('prompt_versions') as batch_op:
        batch_op.alter_column(
            'path',
            existing_type=sa.String(length=16),
            type_=sa.String(length=1),
            existing_nullable=False,
            existing_server_default='1',
        )
