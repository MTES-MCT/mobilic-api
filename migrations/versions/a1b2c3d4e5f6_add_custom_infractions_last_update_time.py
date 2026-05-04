"""add custom infractions last update time

Revision ID: a1b2c3d4e5f6
Revises: f8a1b2c3d4e5
Create Date: 2026-04-27 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f8a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column(
            "reported_custom_infractions_last_update_time",
            sa.DateTime,
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "controller_control", "reported_custom_infractions_last_update_time"
    )
