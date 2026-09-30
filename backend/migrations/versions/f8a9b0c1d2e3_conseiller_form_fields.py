"""Comptes conseiller: the fields the PM's 2026-09-30 demande form asks for

Eight columns on counselor_profiles: the applicant's name, the structure's type
(with a free-text slot when « Autre » is picked), its SIRET, its address split
into three, and the domains it works in.

All nullable. The demandes already in production answered none of these, and a
NOT NULL column would need a backfill of invented data to add. The route
requires them of new submissions instead, which is where the rule belongs.

email_pro and message are deliberately NOT dropped. The PM merged the
professional email into the account email and removed « Précisions », so
nothing asks for either any more — but rows written while they were asked keep
their answers, the same way profiles.rayon was retired rather than deleted.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-30
"""
import sqlalchemy as sa
from alembic import op


revision = 'f8a9b0c1d2e3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


COLUMNS = (
    ("nom_complet", sa.String(255)),
    ("type_structure", sa.String(64)),
    ("type_structure_autre", sa.String(255)),
    ("siret", sa.String(14)),
    ("adresse_rue", sa.String(255)),
    ("adresse_code_postal", sa.String(16)),
    ("adresse_ville", sa.String(128)),
    ("domaines", sa.JSON()),
)


def _columns(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("counselor_profiles")}


def upgrade():
    # Idempotent per this repo's convention: entrypoint.sh runs `db upgrade` at
    # container start, and a half-applied revision must not wedge the backend.
    # Each column is guarded on its own name, so a crash part-way through leaves
    # the rest to be added on the next boot.
    have = _columns(op.get_bind())
    for name, type_ in COLUMNS:
        if name not in have:
            op.add_column("counselor_profiles", sa.Column(name, type_, nullable=True))


def downgrade():
    have = _columns(op.get_bind())
    for name, _ in reversed(COLUMNS):
        if name in have:
            op.drop_column("counselor_profiles", name)
