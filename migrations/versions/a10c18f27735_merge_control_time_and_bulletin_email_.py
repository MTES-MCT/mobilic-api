"""Merge control_time and bulletin email features

Revision ID: a10c18f27735
Revises: 6f02aa230fcc, 1b0149fade1a
Create Date: 2025-10-31 14:57:17.212101

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a10c18f27735"
down_revision = ("6f02aa230fcc", "1b0149fade1a")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
