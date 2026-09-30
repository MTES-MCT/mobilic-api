"""add_refresh_token_rotation_columns

Add consumed_at and replaced_by_token to refresh_token and
controller_refresh_token to support atomic rotation with a reuse grace
period (Trello iNB3yLD6). A consumed token is kept until purge so a client
replaying it shortly after (lost response, concurrent tabs) can recover the
successor tokens instead of being logged out.

Revision ID: d4f8b2c6e1a9
Revises: c8f1a2b3d4e5
Create Date: 2026-08-05 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d4f8b2c6e1a9"
down_revision = "c8f1a2b3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "refresh_token",
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "refresh_token",
        sa.Column("replaced_by_token", sa.String(128), nullable=True),
    )
    op.add_column(
        "controller_refresh_token",
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "controller_refresh_token",
        sa.Column("replaced_by_token", sa.String(128), nullable=True),
    )


def downgrade():
    op.drop_column("controller_refresh_token", "replaced_by_token")
    op.drop_column("controller_refresh_token", "consumed_at")
    op.drop_column("refresh_token", "replaced_by_token")
    op.drop_column("refresh_token", "consumed_at")
