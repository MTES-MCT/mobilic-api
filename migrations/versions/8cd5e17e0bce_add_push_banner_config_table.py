"""add push_banner_config table

Revision ID: 8cd5e17e0bce
Revises: 7b5105df37d1
Create Date: 2026-08-06 16:32:03.054416

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8cd5e17e0bce'
down_revision = '7b5105df37d1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('push_banner_config',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('banner_text', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['updated_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('push_banner_config')
