"""update mission validation auto validations

Revision ID: 4d83f466b18c
Revises: 8bc3c981ee6a
Create Date: 2025-04-24 11:26:30.252720

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4d83f466b18c"
down_revision = "8bc3c981ee6a"
branch_labels = None
depends_on = None


def upgrade():

    op.add_column(
        "mission_validation", sa.Column("is_auto", sa.Boolean(), nullable=True)
    )
    op.execute("UPDATE mission_validation SET is_auto = false")
    op.alter_column("mission_validation", "is_auto", nullable=False)

    op.alter_column(
        "mission_validation",
        "submitter_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    op.drop_constraint(
        "non_admin_can_only_validate_for_self",
        "mission_validation",
        type_="check",
    )
    op.create_check_constraint(
        "non_admin_can_only_validate_for_self",
        "mission_validation",
        "is_auto OR is_admin OR (submitter_id IS NOT NULL AND user_id = submitter_id)",
    )

    op.create_check_constraint(
        "auto_requires_null_submitter",
        "mission_validation",
        "NOT is_auto OR submitter_id IS NULL",
    )

    op.alter_column(
        "mission_end",
        "submitter_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "mission_end",
        "submitter_id",
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.alter_column(
        "mission_validation",
        "submitter_id",
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.drop_column("mission_validation", "is_auto")
    op.create_check_constraint(
        "non_admin_can_only_validate_for_self",
        "mission_validation",
        "(is_admin OR (user_id = submitter_id))",
    )
