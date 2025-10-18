"""Merge multiple heads after revert/reapply cycle

Revision ID: 20b56cbd2d05
Revises: 349352e8308d, 96ec09166d4a
Create Date: 2025-10-01 11:10:55.427213

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20b56cbd2d05"
down_revision = ("349352e8308d", "96ec09166d4a")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
