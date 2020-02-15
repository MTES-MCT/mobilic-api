"""Add driver switch activity status

Revision ID: 8fde055f9d29
Revises: 8fe63e4276dc
Create Date: 2020-02-15 16:46:48.890628

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8fde055f9d29"
down_revision = "8fe63e4276dc"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("activityvalidationstatus", "activity")
    op.alter_column(
        "activity",
        "validation_status",
        type_=sa.Enum(
            "no_activity_switch",
            "driver_switch",
            "unauthorized_submitter",
            "conflicting_with_history",
            "validated",
            "pending",
            "rejected",
            name="activityvalidationstatus",
            native_enum=False,
        ),
        nullable=False,
    )
    # ### end Alembic commands ###


def downgrade():
    op.drop_constraint("activityvalidationstatus", "activity")
    op.alter_column(
        "activity",
        "validation_status",
        type_=sa.Enum(
            "no_activity_switch",
            "unauthorized_submitter",
            "conflicting_with_history",
            "validated",
            "pending",
            "rejected",
            name="activityvalidationstatus",
            native_enum=False,
        ),
        nullable=False,
    )
    # ### end Alembic commands ###
