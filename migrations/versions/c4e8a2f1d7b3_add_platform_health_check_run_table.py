"""add platform_health_check_run table

Revision ID: c4e8a2f1d7b3
Revises: 9c91def65391
Create Date: 2026-11-18 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c4e8a2f1d7b3"
down_revision = "9c91def65391"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_health_check_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column(
            "failures", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("platform_health_check_run")
