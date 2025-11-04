"""Add delivered_by_hand and sent_to_admin columns to controller_control

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
        sa.Column("sent_to_admin", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "controller_control",
        sa.Column(
            "control_bulletin_update_time", sa.DateTime(), nullable=True
        ),
    )

    conn = op.get_bind()
    conn.execute(
        """
        UPDATE controller_control
        SET control_bulletin_update_time = control_bulletin_creation_time
        WHERE control_bulletin_creation_time IS NOT NULL
        """
    )


def downgrade():
    op.drop_column("controller_control", "sent_to_admin")
    op.drop_column("controller_control", "delivered_by_hand")
    op.drop_column("controller_control", "control_bulletin_update_time")
