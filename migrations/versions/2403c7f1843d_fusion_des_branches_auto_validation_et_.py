"""fusion des branches auto validation et notifications

Revision ID: 2403c7f1843d
Revises: 890469f396e6, 4ebd50b0ef82
Create Date: 2025-07-03 17:39:09.393612

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2403c7f1843d"
down_revision = ("890469f396e6", "4ebd50b0ef82")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
