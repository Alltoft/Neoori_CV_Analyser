"""Add the « Ton parcours » block to profiles

Four columns for the block the PM places after session 1: the level reached,
the kind of schooling, its exact name, and the appetite for short or long
studies. The last one is the one that filters the pistes — without it nothing
can say whether a piste is reachable for this person.

All four are nullable. Every profile written before this block existed stays
valid and keeps saving; the questions are asked once, inside the voyage, not
retro-demanded from anyone.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-09-18
"""
import sqlalchemy as sa
from alembic import op


revision = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


COLUMNS = (
    ("diplome", sa.String(32)),
    ("type_etudes", sa.String(32)),
    ("intitule_etudes", sa.Text()),
    ("appetence_etudes", sa.String(16)),
)


def _existing(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("profiles")}


def upgrade():
    # Idempotent: the deploy runbook and entrypoint.sh both run `db upgrade`,
    # and a half-applied revision must not wedge the container at start.
    have = _existing(op.get_bind())
    for name, type_ in COLUMNS:
        if name not in have:
            op.add_column("profiles", sa.Column(name, type_, nullable=True))


def downgrade():
    have = _existing(op.get_bind())
    for name, _ in reversed(COLUMNS):
        if name in have:
            op.drop_column("profiles", name)
