"""Record the consent bloc 5 and the OETH flag need of their own

Those two are health-adjacent and a disability status — GDPR Art. 9 — and the
CGV tick taken at signup, before the person had seen the product, is neither
specific nor informed for them. Two nullable columns hold the second consent:
when it was given, and under which wording.

Null for everyone who never opened the conditions step, which is most people.
Rows written before this revision keep their bloc 5: the gate asks for the tick
on the next write, not retroactively.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-18
"""
import sqlalchemy as sa
from alembic import op


revision = 'd6e7f8a9b0c1'
down_revision = 'c5d6e7f8a9b0'
branch_labels = None
depends_on = None


COLUMNS = (
    ("consent_sensitive_at", sa.DateTime()),
    ("consent_sensitive_version", sa.String(16)),
)


def _existing(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("profiles")}


def upgrade():
    # Idempotent: entrypoint.sh runs `db upgrade` at container start, and a
    # half-applied revision must not wedge the backend down.
    have = _existing(op.get_bind())
    for name, type_ in COLUMNS:
        if name not in have:
            op.add_column("profiles", sa.Column(name, type_, nullable=True))


def downgrade():
    have = _existing(op.get_bind())
    for name, _ in reversed(COLUMNS):
        if name in have:
            op.drop_column("profiles", name)
