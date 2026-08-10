"""add context to mission_validation

Revision ID: f3aa24f6aa1c
Revises: ed3f60d26a7a
Create Date: 2026-07-14 12:34:19.076166

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f3aa24f6aa1c'
down_revision = 'ed3f60d26a7a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'mission_validation',
        sa.Column('context', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_column('mission_validation', 'context')
