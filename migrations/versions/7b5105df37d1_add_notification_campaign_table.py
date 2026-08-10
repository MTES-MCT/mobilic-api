"""add notification_campaign table

Revision ID: 7b5105df37d1
Revises: f7c4a3ecdff9
Create Date: 2026-08-05 09:45:23.395190

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7b5105df37d1'
down_revision = 'f7c4a3ecdff9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notification_campaign',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('creation_time', sa.DateTime(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('target_type', sa.Enum(
            'all_users', 'all_employees', 'all_managers',
            'specific_employees', 'specific_managers',
            name='campaigntargettype', native_enum=False,
        ), nullable=False),
        sa.Column('target_user_ids', postgresql.JSONB(
            none_as_null=True, astext_type=sa.Text(),
        ), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum(
            'draft', 'sending', 'sent', 'cancelled', 'failed',
            name='campaignstatus', native_enum=False,
        ), server_default='draft', nullable=False),
        sa.Column('total_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('sent_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('clicked_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_notification_campaign_created_by_id'),
        'notification_campaign', ['created_by_id'], unique=False,
    )


def downgrade():
    op.drop_index(
        op.f('ix_notification_campaign_created_by_id'),
        table_name='notification_campaign',
    )
    op.drop_table('notification_campaign')
