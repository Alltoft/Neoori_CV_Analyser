"""Comptes conseiller: demandes, code ownership, redemption log

Three changes, one revision:

  * counselor_profiles — one demande per account, carrying the two admin dials
    (max_codes, max_uses_per_code). Nothing is added to `users`.
  * counselor_codes — owner_id, max_uses, expires_at, revoked_at, every one
    nullable so the rows that exist keep behaving exactly as they did: unowned,
    unlimited, unexpiring.
  * code_redemptions — who redeemed what, when. uses_count is an integer and
    answers none of that.

code_redemptions.user_id is ON DELETE SET NULL: erasing an account must leave
the conseiller's count intact and the person gone.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-24
"""
import sqlalchemy as sa
from alembic import op


revision = 'e7f8a9b0c1d2'
down_revision = 'd6e7f8a9b0c1'
branch_labels = None
depends_on = None


CODE_COLUMNS = (
    ("owner_id", sa.String(36)),
    ("max_uses", sa.Integer()),
    ("expires_at", sa.DateTime()),
    ("revoked_at", sa.DateTime()),
)


def _tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    # Idempotent: entrypoint.sh runs `db upgrade` at container start, and a
    # half-applied revision must not wedge the backend down.
    bind = op.get_bind()
    tables = _tables(bind)

    if "counselor_profiles" not in tables:
        op.create_table(
            "counselor_profiles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("structure", sa.String(255), nullable=False),
            sa.Column("fonction", sa.String(255), nullable=False),
            sa.Column("telephone", sa.String(32), nullable=False),
            sa.Column("email_pro", sa.String(255), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.Enum("pending", "approved", "rejected", "revoked", name="counselor_status"),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("max_codes", sa.Integer(), nullable=True),
            sa.Column("max_uses_per_code", sa.Integer(), nullable=True),
            sa.Column("decision_reason", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", name="uq_counselor_profiles_user"),
        )
        op.create_index("ix_counselor_profiles_status", "counselor_profiles", ["status"])

    have = _columns(bind, "counselor_codes")
    for name, type_ in CODE_COLUMNS:
        if name not in have:
            op.add_column("counselor_codes", sa.Column(name, type_, nullable=True))
    if "owner_id" not in have:
        op.create_index("ix_counselor_codes_owner_id", "counselor_codes", ["owner_id"])
        # batch_alter_table for the FK alone. SQLite has no ALTER-of-constraint, and
        # replaying this chain against a scratch SQLite file is a rehearsal this repo
        # supports today (a3b4c5d6e7f8 and e1f2a3b4c5d6 keep it working the same way).
        # add_column and create_index need no batch — they already run on SQLite, and
        # bare calls are what d6e7f8a9b0c1 and c5d6e7f8a9b0 use. On MySQL batch mode
        # passes straight through to a normal ALTER.
        with op.batch_alter_table("counselor_codes") as batch_op:
            batch_op.create_foreign_key(
                "fk_counselor_codes_owner_id", "users", ["owner_id"], ["id"]
            )

    if "code_redemptions" not in tables:
        op.create_table(
            "code_redemptions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code_id", sa.String(36), sa.ForeignKey("counselor_codes.id"), nullable=False),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "target_type",
                sa.Enum("analysis", "voyage", name="redemption_target"),
                nullable=False,
            ),
            sa.Column("target_id", sa.String(36), nullable=False),
            sa.Column("redeemed_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "code_id", "target_type", "target_id", name="uq_code_redemptions_target"
            ),
        )
        op.create_index("ix_code_redemptions_code_id", "code_redemptions", ["code_id"])
        op.create_index("ix_code_redemptions_user_id", "code_redemptions", ["user_id"])
        op.create_index("ix_code_redemptions_redeemed_at", "code_redemptions", ["redeemed_at"])


def downgrade():
    bind = op.get_bind()
    tables = _tables(bind)

    if "code_redemptions" in tables:
        op.drop_table("code_redemptions")

    have = _columns(bind, "counselor_codes")
    if "owner_id" in have:
        with op.batch_alter_table("counselor_codes") as batch_op:
            batch_op.drop_constraint("fk_counselor_codes_owner_id", type_="foreignkey")
        op.drop_index("ix_counselor_codes_owner_id", table_name="counselor_codes")
    for name, _ in reversed(CODE_COLUMNS):
        if name in have:
            op.drop_column("counselor_codes", name)

    if "counselor_profiles" in tables:
        op.drop_table("counselor_profiles")
