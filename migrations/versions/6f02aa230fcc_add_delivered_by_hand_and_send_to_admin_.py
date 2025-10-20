"""Add delivered_by_hand and send_to_admin columns to controller_control

Revision ID: 6f02aa230fcc
Revises: 20b56cbd2d05
Create Date: 2025-10-14 08:46:28.840551

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6f02aa230fcc"
down_revision = "20b56cbd2d05"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column("delivered_by_hand", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "controller_control",
        sa.Column("send_to_admin", sa.Boolean(), nullable=True),
    )


def downgrade():
    op.drop_column("controller_control", "send_to_admin")
    op.drop_column("controller_control", "delivered_by_hand")
