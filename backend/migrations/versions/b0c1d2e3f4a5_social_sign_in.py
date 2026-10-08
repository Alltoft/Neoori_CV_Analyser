"""Social sign-in: auth_identities and login_links

auth_identities ties a Google or Microsoft account (provider + the ID token's
sub) to a users row; subject compares case-sensitively (utf8mb4_bin).
login_links is the email sign-in link's single-use record and pacing clock;
it holds an HMAC of the address, never the address.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-10-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = 'b0c1d2e3f4a5'
down_revision = 'a9b0c1d2e3f4'
branch_labels = None
depends_on = None


def _tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _indexes(bind, table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table)}


def upgrade():
    # Idempotent per this repo's convention: entrypoint.sh runs `db upgrade`
    # at container start, and MySQL DDL is not transactional — each guard
    # checks the very object it is about to create, so a crash between two
    # statements resumes at the one that did not happen.
    bind = op.get_bind()

    if "auth_identities" not in _tables(bind):
        op.create_table(
            "auth_identities",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "user_id", sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("provider", sa.String(16), nullable=False),
            sa.Column(
                "subject",
                sa.String(255).with_variant(mysql.VARCHAR(255, collation="utf8mb4_bin"), "mysql"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("provider", "subject", name="uq_auth_identities_provider_subject"),
        )
    if "ix_auth_identities_user_id" not in _indexes(bind, "auth_identities"):
        op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])

    if "login_links" not in _tables(bind):
        op.create_table(
            "login_links",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email_hash", sa.CHAR(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
        )
    if "ix_login_links_email_hash_created_at" not in _indexes(bind, "login_links"):
        op.create_index(
            "ix_login_links_email_hash_created_at", "login_links", ["email_hash", "created_at"]
        )


def downgrade():
    tables = _tables(op.get_bind())
    if "login_links" in tables:
        op.drop_table("login_links")
    if "auth_identities" in tables:
        op.drop_table("auth_identities")
