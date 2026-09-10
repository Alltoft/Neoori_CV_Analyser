"""Set ON DELETE SET NULL on analyses.voyage_id

The FK analyses.voyage_id -> voyages.id had no ondelete action, so it
defaulted to NO ACTION (MySQL) / RESTRICT-like behaviour. Once a later phase
starts populating voyage_id, DELETE /api/voyage on a voyage that still has an
analysis pointing at it would be rejected by the database with an
IntegrityError, and the handler had no try/except around it — an RGPD
erasure request would 500 instead of succeeding.

SET NULL (not CASCADE, not RESTRICT) is correct here: erasing a voyage must
not delete the analyses it fed — those are the person's own reports and their
B2G traceability rows — but the link must not dangle either. The column was
already nullable, so SET NULL requires no further schema change.

Altering a FK means dropping and recreating it: batch_alter_table so this
runs on SQLite too, exactly as e1f2a3b4c5d6 (which first created this
constraint) does.

DOWNGRADE NOTE: downgrade() recreates fk_analyses_voyage_id without an
ondelete action, i.e. it reintroduces the original defect (NO ACTION). This
is not lossy of data — no column, index or row is touched — but a database
at this migration's `down_revision` is, once more, unable to delete a voyage
that an analysis still references without the caller's own
IntegrityError handling saving it (see app/routes/voyage.py delete_voyage).

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa


revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('analyses') as batch_op:
        batch_op.drop_constraint('fk_analyses_voyage_id', type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_analyses_voyage_id', 'voyages', ['voyage_id'], ['id'], ondelete='SET NULL'
        )


def downgrade():
    # Reintroduces the original defect (no ondelete action) — see the
    # DOWNGRADE NOTE above. No data is lost by this step itself.
    with op.batch_alter_table('analyses') as batch_op:
        batch_op.drop_constraint('fk_analyses_voyage_id', type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_analyses_voyage_id', 'voyages', ['voyage_id'], ['id']
        )
