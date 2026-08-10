"""merge detachment dispute and impersonation migrations

Revision ID: 0da0a33704b0
Revises: f3aa24f6aa1c, ab318bfc3ec2, f134c8cd7f76
Create Date: 2026-07-20 12:57:38.022015

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0da0a33704b0'
down_revision = ('f3aa24f6aa1c', 'ab318bfc3ec2', 'f134c8cd7f76')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
