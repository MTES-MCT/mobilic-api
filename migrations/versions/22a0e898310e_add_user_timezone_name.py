"""add_user_timezone_name

Revision ID: 22a0e898310e
Revises: 2c97929c18d0
Create Date: 2022-09-01 17:33:48.818171

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "22a0e898310e"
down_revision = "2c97929c18d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("timezone_name", sa.String(length=255)))
    op.execute("UPDATE \"user\" SET timezone_name = 'Europe/Paris'")
    op.alter_column("user", "timezone_name", nullable=False)


def downgrade():
    op.drop_column("user", "timezone_name")
