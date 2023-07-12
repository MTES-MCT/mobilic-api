"""update controller control table

Revision ID: b7270c163b14
Revises: 32ba9730e22c
Create Date: 2023-04-27 17:22:30.669828

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b7270c163b14"
down_revision = "32ba9730e22c"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "controller_control",
        "qr_code_generation_time",
        existing_type=postgresql.TIMESTAMP(),
        nullable=True,
    )
    op.alter_column(
        "controller_control",
        "user_id",
        existing_type=sa.INTEGER(),
        nullable=True,
    )
    op.drop_constraint(
        "only_one_control_per_controller_user_date",
        "controller_control",
        type_="unique",
    )


def downgrade():
    op.create_unique_constraint(
        "only_one_control_per_controller_user_date",
        "controller_control",
        ["controller_id", "user_id", "qr_code_generation_time"],
    )
    op.alter_column(
        "controller_control",
        "user_id",
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.alter_column(
        "controller_control",
        "qr_code_generation_time",
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
    )
