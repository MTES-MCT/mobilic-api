"""anon_controller_control: user_id nullable + control_bulletin_update_time

Revision ID: 68f7e34e43f8
Revises: 4ca13e06a9b5
Create Date: 2026-09-17 15:44:57.223819

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "68f7e34e43f8"
down_revision = "4ca13e06a9b5"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE anon_controller_control "
        "ADD COLUMN IF NOT EXISTS control_bulletin_update_time "
        "TIMESTAMP WITHOUT TIME ZONE"
    )
    op.alter_column(
        "anon_controller_control",
        "user_id",
        existing_type=sa.INTEGER(),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "anon_controller_control",
        "user_id",
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.execute(
        "ALTER TABLE anon_controller_control "
        "DROP COLUMN IF EXISTS control_bulletin_update_time"
    )
