"""Re-heal PromptVersion.path rows still carrying the legacy A/B codes

c3d4e5f6a7b8 already converted A -> 1 and B -> 3, but the seed scripts kept
writing the old codes, so any database seeded after that migration (the VPS,
bootstrapped from a fresh MySQL container) ends up with an active prompt on
path 'A' again. The analysis lookup filters on the parcours id, so every run
died instantly with "Aucun prompt actif pour le chemin 1".

The seed scripts now write parcours ids; this migration repairs the rows they
already wrote. Idempotent — a no-op once no legacy code is left.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-23
"""
from alembic import op


revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE prompt_versions SET path = '1' WHERE path = 'A'")
    op.execute("UPDATE prompt_versions SET path = '3' WHERE path = 'B'")


def downgrade():
    # c3d4e5f6a7b8's downgrade owns the reverse mapping; re-applying it here
    # would fight that migration for the same rows.
    pass
