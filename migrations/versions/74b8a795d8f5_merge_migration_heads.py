"""merge migration heads

Revision ID: 74b8a795d8f5
Revises: 7868983570ba, c8f1a2b3d4e5
Create Date: 2026-08-11 08:25:37.725811

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74b8a795d8f5'
down_revision = ('7868983570ba', 'c8f1a2b3d4e5')
branch_labels = None
depends_on = None


def upgrade():
    # merge only, no schema changes
    pass


def downgrade():
    # merge only, no schema changes
    pass
