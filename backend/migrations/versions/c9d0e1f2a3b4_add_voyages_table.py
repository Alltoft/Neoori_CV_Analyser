"""Create the voyages table

One row per attempt at the six sessions of « le voyage ». Many per user (a
retake is a new row, and analyses reference the one that fed them), at most one
open at a time — the API enforces that, not the schema.

Everything content-bearing is a Fernet token in a Text column: the answers, the
S0 phrase, the portrait. A psychometric read-out is more sensitive than bloc 5,
so the plaintext columns hold only status, timestamps and foreign keys.

Statuses are String(16), never a native enum — widening a MySQL ENUM is the one
migration step this repo cannot rehearse locally.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'voyages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('sessions_completed', sa.JSON(), nullable=False),
        sa.Column('consent_at', sa.DateTime(), nullable=False),
        sa.Column('consent_version', sa.String(length=16), nullable=False),
        sa.Column('age_attested', sa.Boolean(), nullable=False),
        sa.Column('counselor_code_id', sa.String(length=36), nullable=True),
        # Fernet tokens (URL-safe base64), not raw bytes — Text is the right type.
        sa.Column('responses_encrypted', sa.Text(), nullable=True),
        sa.Column('micro_status', sa.String(length=16), nullable=False),
        sa.Column('micro_encrypted', sa.Text(), nullable=True),
        sa.Column('portrait_status', sa.String(length=16), nullable=False),
        sa.Column('portrait_encrypted', sa.Text(), nullable=True),
        sa.Column('portrait_validated_at', sa.DateTime(), nullable=True),
        sa.Column('validated_by_id', sa.String(length=36), nullable=True),
        sa.Column('share_token', sa.String(length=64), nullable=True),
        sa.Column('scoring_version', sa.String(length=16), nullable=False),
        sa.Column('tokens_in', sa.Integer(), nullable=True),
        sa.Column('tokens_out', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_voyages_user_id'),
        sa.ForeignKeyConstraint(['validated_by_id'], ['users.id'],
                                name='fk_voyages_validated_by_id'),
        sa.ForeignKeyConstraint(['counselor_code_id'], ['counselor_codes.id'],
                                name='fk_voyages_counselor_code_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_voyages_user_id', 'voyages', ['user_id'])
    op.create_index('ix_voyages_status', 'voyages', ['status'])
    # unique=True on the index rather than a separate UniqueConstraint: the
    # model declares share_token unique+index, and SQLAlchemy renders that pair
    # as one unique index. Two would mean two indexes on MySQL.
    op.create_index('ix_voyages_share_token', 'voyages', ['share_token'], unique=True)


def downgrade():
    op.drop_index('ix_voyages_share_token', table_name='voyages')
    op.drop_index('ix_voyages_status', table_name='voyages')
    op.drop_index('ix_voyages_user_id', table_name='voyages')
    op.drop_table('voyages')
