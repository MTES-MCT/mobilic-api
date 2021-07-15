"""rename column

Revision ID: dbfe3ea99885
Revises: 9d607a1d2b0a
Create Date: 2021-07-15 10:04:13.475048

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "dbfe3ea99885"
down_revision = "9d607a1d2b0a"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "activity_version", "version", new_column_name="version_number"
    )


def downgrade():
    op.alter_column(
        "activity_version", "version_number", new_column_name="version"
    )
