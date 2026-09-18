"""Erase the billet de sortie from every stored voyage

The billet de sortie dated from the paper cahier, when a counselor filled it in
for the candidate. PM ruling 2026-09-15: it is gone from every session. Nothing
ever read the text — no prompt, no counselor view — so it is erased rather than
kept: data collected for a purpose that no longer exists.

Rewrites voyages.responses_encrypted to {"answers": ...} only. updated_at is
assigned to itself, so MySQL's ON UPDATE cannot move it: the stall rules and the
startup sweep read that clock. A row that cannot be decrypted is left as it is
and logged, never fatal — this runs at container start (entrypoint.sh), where an
exception keeps the backend down — and Voyage.responses no longer serves a
billet from any row, whatever it still holds.

Idempotent. Irreversible: downgrade cannot bring the text back.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-15
"""
import logging

import sqlalchemy as sa
from alembic import op


revision = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


def strip_billets(bind) -> int:
    """Rewrite every voyage whose stored responses still carry "billets".

    Takes a connection, so a test can run it without Alembic. Returns how many
    rows were rewritten.
    """
    from app.utils import crypto

    rows = bind.execute(sa.text(
        "SELECT id, responses_encrypted FROM voyages WHERE responses_encrypted IS NOT NULL"
    )).fetchall()
    rewritten = 0
    for voyage_id, token in rows:
        try:
            payload = crypto.decrypt_json(token)
        except (crypto.DecryptionError, ValueError):
            log.warning("voyage %s: responses not readable, left as they are", voyage_id)
            continue
        if not isinstance(payload, dict) or "billets" not in payload:
            continue
        bind.execute(
            sa.text(
                "UPDATE voyages SET responses_encrypted = :token, updated_at = updated_at "
                "WHERE id = :id"
            ),
            {"token": crypto.encrypt_json({"answers": payload.get("answers") or {}}),
             "id": voyage_id},
        )
        rewritten += 1
    return rewritten


def upgrade():
    count = strip_billets(op.get_bind())
    log.info("billet de sortie erased from %s voyage(s)", count)


def downgrade():
    # The text is gone; there is nothing to restore.
    pass
