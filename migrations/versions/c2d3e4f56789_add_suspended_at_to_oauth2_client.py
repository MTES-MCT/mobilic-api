"""add suspended_at to oauth2_client

Revision ID: c2d3e4f56789
Revises: b1c2d3e4f567
Create Date: 2026-08-07 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c2d3e4f56789"
down_revision = "b1c2d3e4f567"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "oauth2_client",
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("oauth2_client", "suspended_at")
