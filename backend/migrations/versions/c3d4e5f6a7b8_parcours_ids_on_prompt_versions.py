"""Migrate PromptVersion.path from A/B codes to parcours ids

CDC v1.2 replaces the two-path model (A = analyse ciblée, B = orientation)
with three parcours. The column is String(1) and the new ids are single
characters, so only the values change — no width alteration needed.

  A -> 1  (« J'ai une cible »)
  B -> 3  (« Je pars de zéro » — the CV-less journey B was serving)

Parcours 2 (« Je cherche ma direction ») has no prior rows; its prompt is
authored fresh in the admin dashboard.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


# Analysis.inputs is a JSON blob holding "_path" per row. Rewriting it in
# SQL would mean a MySQL-specific JSON_SET that SQLite can't run, and the
# app already normalises legacy codes on read (section_registry.normalize),
# so existing analyses keep rendering untouched. Only prompt_versions —
# which the lookup filters on directly — has to move.

def upgrade():
    op.execute("UPDATE prompt_versions SET path = '1' WHERE path = 'A'")
    op.execute("UPDATE prompt_versions SET path = '3' WHERE path = 'B'")
    # batch mode so the file stays runnable on SQLite, which has no
    # ALTER COLUMN. Production is MySQL/TiDB, where this is a plain ALTER.
    with op.batch_alter_table('prompt_versions') as batch_op:
        batch_op.alter_column(
            'path',
            existing_type=sa.String(length=1),
            nullable=False,
            server_default='1',
        )


def downgrade():
    with op.batch_alter_table('prompt_versions') as batch_op:
        batch_op.alter_column(
            'path',
            existing_type=sa.String(length=1),
            nullable=False,
            server_default='A',
        )
    op.execute("UPDATE prompt_versions SET path = 'A' WHERE path = '1'")
    op.execute("UPDATE prompt_versions SET path = 'B' WHERE path = '3'")
    # Parcours 2 has no pre-v1.2 equivalent; fold it into A so the column
    # keeps satisfying the old ('A','B') contract.
    op.execute("UPDATE prompt_versions SET path = 'A' WHERE path = '2'")
