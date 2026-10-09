"""Four doors: who an analysis is for, and the limits that hold it

analyses gains door, access_token_hash, counselor_id, pending_user_id,
consent_at, consent_version and started_at; ownerless rows written before this
revision are marked door='legacy'. code_redemptions gains slot and two unique
keys; counselor_notes one unique key; run_log is new.

Rolling back past this revision is only safe after
`flask purge-expired --before-rollback --apply` (DOCKER.md, « Rolling back
below the four-doors migration »): without it, advisor-door reports, unclaimed
no-login reports and held drafts become plain ownerless rows, which the
previous image serves to anyone holding the id.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op


revision = 'c1d2e3f4a5b6'
down_revision = 'b0c1d2e3f4a5'
branch_labels = None
depends_on = None


def _inspect(bind):
    return sa.inspect(bind)


def _tables(bind) -> set[str]:
    return set(_inspect(bind).get_table_names())


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in _inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {i["name"] for i in _inspect(bind).get_indexes(table)}


def _uniques(bind, table: str) -> set[str]:
    return {u["name"] for u in _inspect(bind).get_unique_constraints(table)}


def _foreign_keys(bind, table: str) -> set[str]:
    return {fk["name"] for fk in _inspect(bind).get_foreign_keys(table)}


def _analysis_columns():
    return [
        sa.Column("door", sa.String(16), nullable=True),
        sa.Column("access_token_hash", sa.CHAR(64), nullable=True),
        sa.Column("counselor_id", sa.String(36), nullable=True),
        sa.Column("pending_user_id", sa.String(36), nullable=True),
        sa.Column("consent_at", sa.DateTime(), nullable=True),
        sa.Column("consent_version", sa.String(16), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
    ]


def mark_legacy(conn) -> int:
    """Ownerless rows that exist now keep their by-id access (spec decision
    44). Marking them is what makes that explicit: from here on, a row with no
    owner, no token and no counselor is closed, not silently readable."""
    result = conn.execute(sa.text(
        "UPDATE analyses SET door = 'legacy' WHERE user_id IS NULL AND door IS NULL"
    ))
    return result.rowcount


def dedupe_user_redemptions(conn, table: str = "code_redemptions") -> int:
    """Before the (code_id, target_type, user_id) unique key: keep the person
    on their earliest redemption of a code per kind, and null them on the
    later ones. The rows stay, so a spent use stays spent. Prod had no such
    duplicate on 2026-10-08; a dev database may."""
    rows = conn.execute(sa.text(
        f"SELECT id, code_id, target_type, user_id FROM {table} "
        "WHERE user_id IS NOT NULL ORDER BY code_id, target_type, user_id, redeemed_at, id"
    )).fetchall()
    seen, nulled = set(), 0
    for rid, code_id, kind, user_id in rows:
        key = (code_id, kind, user_id)
        if key in seen:
            conn.execute(sa.text(f"UPDATE {table} SET user_id = NULL WHERE id = :id"), {"id": rid})
            nulled += 1
        seen.add(key)
    return nulled


def backfill_slots(conn) -> int:
    """Number the existing redemptions of limited codes 1..n per (code, kind),
    in redemption order, continuing after any slot already written — so a
    crash halfway resumes cleanly and the unique slot key holds from the first
    new redemption."""
    rows = conn.execute(sa.text(
        "SELECT r.id, r.code_id, r.target_type, r.slot FROM code_redemptions r "
        "JOIN counselor_codes c ON c.id = r.code_id "
        "WHERE c.max_uses IS NOT NULL "
        "ORDER BY r.code_id, r.target_type, r.redeemed_at, r.id"
    )).fetchall()
    top: dict[tuple[str, str], int] = {}
    for _rid, code_id, kind, slot in rows:
        if slot is not None:
            top[(code_id, kind)] = max(top.get((code_id, kind), 0), slot)
    filled = 0
    for rid, code_id, kind, slot in rows:
        if slot is None:
            top[(code_id, kind)] = top.get((code_id, kind), 0) + 1
            conn.execute(
                sa.text("UPDATE code_redemptions SET slot = :s WHERE id = :id"),
                {"s": top[(code_id, kind)], "id": rid},
            )
            filled += 1
    return filled


def upgrade():
    # Idempotent per this repo's convention (b0c1d2e3f4a5): entrypoint.sh runs
    # `db upgrade` at container start, and MySQL DDL is not transactional.
    bind = op.get_bind()

    existing = _columns(bind, "analyses")
    for column in _analysis_columns():
        if column.name not in existing:
            op.add_column("analyses", column)

    fks = _foreign_keys(bind, "analyses")
    for name, column in (
        ("fk_analyses_counselor_id_users", "counselor_id"),
        ("fk_analyses_pending_user_id_users", "pending_user_id"),
    ):
        if name not in fks:
            op.create_foreign_key(name, "analyses", "users", [column], ["id"], ondelete="SET NULL")

    indexes = _indexes(bind, "analyses")
    if "ix_analyses_door_created_at" not in indexes:
        op.create_index("ix_analyses_door_created_at", "analyses", ["door", "created_at"])
    if "ix_analyses_counselor_id" not in indexes:
        op.create_index("ix_analyses_counselor_id", "analyses", ["counselor_id"])
    if "ix_analyses_pending_user_id" not in indexes:
        op.create_index("ix_analyses_pending_user_id", "analyses", ["pending_user_id"])
    if "uq_analyses_access_token_hash" not in indexes | _uniques(bind, "analyses"):
        op.create_index(
            "uq_analyses_access_token_hash", "analyses", ["access_token_hash"], unique=True
        )

    mark_legacy(bind)

    if "slot" not in _columns(bind, "code_redemptions"):
        op.add_column("code_redemptions", sa.Column("slot", sa.Integer(), nullable=True))
    dedupe_user_redemptions(bind)
    backfill_slots(bind)
    uniques = _uniques(bind, "code_redemptions") | _indexes(bind, "code_redemptions")
    if "uq_code_redemptions_slot" not in uniques:
        op.create_unique_constraint(
            "uq_code_redemptions_slot", "code_redemptions", ["code_id", "target_type", "slot"]
        )
    if "uq_code_redemptions_user" not in uniques:
        op.create_unique_constraint(
            "uq_code_redemptions_user", "code_redemptions", ["code_id", "target_type", "user_id"]
        )

    if "uq_counselor_notes_analysis_counselor" not in (
        _uniques(bind, "counselor_notes") | _indexes(bind, "counselor_notes")
    ):
        op.create_unique_constraint(
            "uq_counselor_notes_analysis_counselor", "counselor_notes",
            ["analysis_id", "counselor_id"],
        )

    if "run_log" not in _tables(bind):
        op.create_table(
            "run_log",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("door", sa.String(16), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    run_log_indexes = _indexes(bind, "run_log")
    if "ix_run_log_door_created_at" not in run_log_indexes:
        op.create_index("ix_run_log_door_created_at", "run_log", ["door", "created_at"])
    if "ix_run_log_user_id_created_at" not in run_log_indexes:
        op.create_index("ix_run_log_user_id_created_at", "run_log", ["user_id", "created_at"])


def downgrade():
    bind = op.get_bind()
    if "run_log" in _tables(bind):
        op.drop_table("run_log")

    if "uq_counselor_notes_analysis_counselor" in (
        _uniques(bind, "counselor_notes") | _indexes(bind, "counselor_notes")
    ):
        op.drop_constraint("uq_counselor_notes_analysis_counselor", "counselor_notes", type_="unique")

    uniques = _uniques(bind, "code_redemptions") | _indexes(bind, "code_redemptions")
    for name in ("uq_code_redemptions_user", "uq_code_redemptions_slot"):
        if name in uniques:
            op.drop_constraint(name, "code_redemptions", type_="unique")
    if "slot" in _columns(bind, "code_redemptions"):
        op.drop_column("code_redemptions", "slot")

    fks = _foreign_keys(bind, "analyses")
    for name in ("fk_analyses_pending_user_id_users", "fk_analyses_counselor_id_users"):
        if name in fks:
            op.drop_constraint(name, "analyses", type_="foreignkey")
    indexes = _indexes(bind, "analyses")
    for name in ("uq_analyses_access_token_hash", "ix_analyses_pending_user_id",
                 "ix_analyses_counselor_id", "ix_analyses_door_created_at"):
        if name in indexes:
            op.drop_index(name, table_name="analyses")
    existing = _columns(bind, "analyses")
    for column in reversed(_analysis_columns()):
        if column.name in existing:
            op.drop_column("analyses", column.name)
