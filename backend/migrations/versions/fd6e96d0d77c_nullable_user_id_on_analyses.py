"""nullable user_id on analyses

Revision ID: fd6e96d0d77c
Revises: e9a0e064023b
Create Date: 2026-05-11 19:58:02.909441

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'fd6e96d0d77c'
down_revision = 'e9a0e064023b'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE"
        " WHERE TABLE_NAME='analyses' AND TABLE_SCHEMA=DATABASE()"
        " AND COLUMN_NAME='user_id' AND REFERENCED_TABLE_NAME='users' LIMIT 1"
    ))
    fk_name = result.scalar()
    if fk_name:
        conn.execute(sa.text(f"ALTER TABLE analyses DROP FOREIGN KEY `{fk_name}`"))
    op.execute("ALTER TABLE analyses MODIFY COLUMN user_id VARCHAR(36) NULL")
    op.execute("ALTER TABLE analyses ADD CONSTRAINT fk_analyses_user_id FOREIGN KEY (user_id) REFERENCES users(id)")


def downgrade():
    op.execute("ALTER TABLE analyses DROP FOREIGN KEY fk_analyses_user_id")
    op.execute("ALTER TABLE analyses MODIFY COLUMN user_id VARCHAR(36) NOT NULL")
    op.execute("ALTER TABLE analyses ADD CONSTRAINT fk_analyses_user_id FOREIGN KEY (user_id) REFERENCES users(id)")
