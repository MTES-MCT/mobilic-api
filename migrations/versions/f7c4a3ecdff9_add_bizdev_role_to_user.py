"""add bizdev role to user

Revision ID: f7c4a3ecdff9
Revises: f3fe9f865a11
Create Date: 2026-08-03 16:11:18.269246

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f7c4a3ecdff9'
down_revision = 'f3fe9f865a11'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column(
        'bizdev', sa.Boolean(),
        nullable=False, server_default='false'
    ))


def downgrade():
    op.drop_column('user', 'bizdev')
