"""Add 'premium' to the user_plan enum

CDC v1.2 adds a third tier above the 9 € paid plan: Premium bundles the
interview-prep module (§10) and the difficult-questions module (§11).

user_plan is a native MySQL ENUM, so widening it needs an explicit
MODIFY COLUMN — SQLAlchemy will not infer it.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite has no ENUM type — it stores these as VARCHAR with a CHECK, and
    # batch mode would rebuild the table for nothing. Only MySQL needs this.
    if op.get_bind().dialect.name != "mysql":
        return
    op.alter_column(
        'users', 'plan',
        existing_type=sa.Enum('free', 'paid', name='user_plan'),
        type_=sa.Enum('free', 'paid', 'premium', name='user_plan'),
        existing_nullable=False,
    )


def downgrade():
    if op.get_bind().dialect.name != "mysql":
        return
    # Premium users fall back to paid rather than losing access entirely.
    op.execute("UPDATE users SET plan = 'paid' WHERE plan = 'premium'")
    op.alter_column(
        'users', 'plan',
        existing_type=sa.Enum('free', 'paid', 'premium', name='user_plan'),
        type_=sa.Enum('free', 'paid', name='user_plan'),
        existing_nullable=False,
    )
