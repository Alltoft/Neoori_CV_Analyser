"""Persistent Profil de base, with the sensitive half in its own table

PM ruling (2026-07-29): B2G accompaniment — Appuis Spécifiques, Aide 18,
Emploi Accompagné — depends on a counselor coming back into the file, so
the profile has to survive the analysis. Two-speed storage:

  profiles            erasable under consent, plaintext
  sensitive_profiles  bloc 5 + OETH, ciphertext, separate table

Separate tables rather than nullable columns on one row, so a DB export or
an admin query over `profiles` cannot surface the sensitive half at all.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('prenom', sa.String(length=120), nullable=True),
        sa.Column('nom', sa.String(length=120), nullable=True),
        sa.Column('ville', sa.String(length=160), nullable=True),
        sa.Column('rayon', sa.String(length=24), nullable=True),
        sa.Column('tranche_age', sa.String(length=16), nullable=True),
        sa.Column('situation', sa.String(length=32), nullable=True),
        sa.Column('reconversion_scope', sa.String(length=32), nullable=True),
        sa.Column('projet', sa.Text(), nullable=True),
        sa.Column('projet_document', sa.Text(), nullable=True),
        sa.Column('contraintes_pratiques', sa.Text(), nullable=True),
        sa.Column('consent_at', sa.DateTime(), nullable=True),
        sa.Column('consent_version', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_profiles_user_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_profiles_user_id'),
    )
    op.create_index('ix_profiles_user_id', 'profiles', ['user_id'])

    op.create_table(
        'sensitive_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('profile_id', sa.String(length=36), nullable=False),
        # Fernet tokens, not raw bytes.
        sa.Column('conditions_encrypted', sa.Text(), nullable=True),
        sa.Column('oeth_encrypted', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'],
                                name='fk_sensitive_profiles_profile_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_id', name='uq_sensitive_profiles_profile_id'),
    )
    op.create_index('ix_sensitive_profiles_profile_id', 'sensitive_profiles', ['profile_id'])


def downgrade():
    op.drop_index('ix_sensitive_profiles_profile_id', table_name='sensitive_profiles')
    op.drop_table('sensitive_profiles')
    op.drop_index('ix_profiles_user_id', table_name='profiles')
    op.drop_table('profiles')
