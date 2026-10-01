"""Email verification: two columns on users, existing accounts backfilled

email_verified_at is NULL until an address is proven; no session is issued
before that. auth_mail_sent_at paces the verification and reset mails.

Every account that exists when this runs is a test account (developer,
2026-09-29), so all of them are marked verified at their signup time rather
than locked out until someone clicks a link nobody will send.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-10-01
"""
import sqlalchemy as sa
from alembic import op


revision = 'a9b0c1d2e3f4'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


COLUMNS = (
    ("email_verified_at", sa.DateTime()),
    ("auth_mail_sent_at", sa.DateTime()),
)


def _columns(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("users")}


def backfill(bind) -> None:
    """Existing accounts count as verified, at their own signup time."""
    bind.execute(sa.text(
        "UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL"
    ))


def upgrade():
    # Idempotent per this repo's convention: entrypoint.sh runs `db upgrade` at
    # container start, and a half-applied revision must not wedge the backend.
    bind = op.get_bind()
    have = _columns(bind)
    for name, type_ in COLUMNS:
        if name not in have:
            op.add_column("users", sa.Column(name, type_, nullable=True))
    backfill(bind)


def downgrade():
    have = _columns(op.get_bind())
    for name, _ in reversed(COLUMNS):
        if name in have:
            op.drop_column("users", name)
