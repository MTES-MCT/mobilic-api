"""add push_subscription table

Revision ID: f3fe9f865a11
Revises: ed3f60d26a7a
Create Date: 2026-07-16 15:37:57.438660

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f3fe9f865a11'
down_revision = 'ed3f60d26a7a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('push_subscription',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('creation_time', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('p256dh_key', sa.Text(), nullable=False),
        sa.Column('auth_key', sa.Text(), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint')
    )
    op.create_index('ix_push_subscription_user_id', 'push_subscription', ['user_id'])


def downgrade():
    op.drop_index('ix_push_subscription_user_id', table_name='push_subscription')
    op.drop_table('push_subscription')
