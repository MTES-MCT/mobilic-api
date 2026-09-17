"""add targeted_count to notification_campaign

Revision ID: 7868983570ba
Revises: 8cd5e17e0bce
Create Date: 2026-08-07 13:58:23.422359

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7868983570ba'
down_revision = '8cd5e17e0bce'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notification_campaign', sa.Column(
        'targeted_count', sa.Integer(),
        server_default='0', nullable=False
    ))


def downgrade():
    op.drop_column('notification_campaign', 'targeted_count')
