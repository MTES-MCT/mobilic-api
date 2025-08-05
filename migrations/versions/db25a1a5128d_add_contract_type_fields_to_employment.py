"""Add contract type fields to employment

Revision ID: db25a1a5128d
Revises: 68ed4db9ae15
Create Date: 2025-08-03 17:24:25.732148

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "db25a1a5128d"
down_revision = "68ed4db9ae15"
branch_labels = None
depends_on = None


def upgrade():
    contract_type_enum = sa.Enum("FULL_TIME", "PART_TIME", name="contracttype")
    contract_type_enum.create(op.get_bind())

    op.add_column(
        "employment",
        sa.Column("contract_type", contract_type_enum, nullable=True),
    )
    op.add_column(
        "employment",
        sa.Column("part_time_percentage", sa.Integer(), nullable=True),
    )
    op.add_column(
        "employment",
        sa.Column("contract_type_snooze_date", sa.Date(), nullable=True),
    )

    op.create_check_constraint(
        "check_part_time_percentage_range",
        "employment",
        "part_time_percentage IS NULL OR (part_time_percentage >= 10 AND part_time_percentage <= 90)",
    )


def downgrade():
    op.drop_constraint("check_part_time_percentage_range", "employment")

    op.drop_column("employment", "contract_type_snooze_date")
    op.drop_column("employment", "part_time_percentage")
    op.drop_column("employment", "contract_type")

    contract_type_enum = sa.Enum("FULL_TIME", "PART_TIME", name="contracttype")
    contract_type_enum.drop(op.get_bind())
