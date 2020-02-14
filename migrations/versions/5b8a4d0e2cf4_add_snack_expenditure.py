"""Add snack expenditure

Revision ID: 5b8a4d0e2cf4
Revises: 2fc4745e5ad8
Create Date: 2020-02-14 03:55:36.458674

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5b8a4d0e2cf4"
down_revision = "2fc4745e5ad8"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("expendituretypes", "expenditure")
    op.alter_column(
        "expenditure",
        "type",
        type_=sa.Enum(
            "day_meal",
            "night_meal",
            "sleep_over",
            "snack",
            name="expendituretypes",
            native_enum=False,
        ),
        nullable=False,
    )


def downgrade():
    op.drop_constraint("expendituretypes", "expenditure")
    op.alter_column(
        "expenditure",
        "type",
        type_=sa.Enum(
            "day_meal",
            "night_meal",
            "sleep_over",
            name="expendituretypes",
            native_enum=False,
        ),
        nullable=False,
    )
