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
    # MySQL 8 rejects ALTER COLUMN while FK constraint is active — drop, alter, recreate
    op.execute("ALTER TABLE analyses DROP FOREIGN KEY analyses_ibfk_2")
    op.execute("ALTER TABLE analyses MODIFY COLUMN user_id VARCHAR(36) NULL")
    op.execute("ALTER TABLE analyses ADD CONSTRAINT analyses_ibfk_2 FOREIGN KEY (user_id) REFERENCES users(id)")


def downgrade():
    op.execute("ALTER TABLE analyses DROP FOREIGN KEY analyses_ibfk_2")
    op.execute("ALTER TABLE analyses MODIFY COLUMN user_id VARCHAR(36) NOT NULL")
    op.execute("ALTER TABLE analyses ADD CONSTRAINT analyses_ibfk_2 FOREIGN KEY (user_id) REFERENCES users(id)")
