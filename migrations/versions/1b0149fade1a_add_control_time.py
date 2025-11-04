"""add control time

Revision ID: 1b0149fade1a
Revises: 20b56cbd2d05
Create Date: 2025-10-14 14:01:52.702205

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1b0149fade1a"
down_revision = "20b56cbd2d05"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column("control_time", sa.DateTime(), nullable=True),
    )

    conn = op.get_bind()
    conn.execute(
        """
        UPDATE controller_control
        SET control_time = COALESCE(qr_code_generation_time, creation_time)
    """
    )

    op.alter_column("controller_control", "control_time", nullable=False)


def downgrade():
    op.drop_column("controller_control", "control_time")
