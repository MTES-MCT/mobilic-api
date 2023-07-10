"""scenario testing - certificate info

Revision ID: 83ea61a446f8
Revises: d342aeb2a88f
Create Date: 2023-07-03 18:38:11.808176

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "83ea61a446f8"
down_revision = "d342aeb2a88f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scenario_testing",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "scenario",
            sa.Enum(
                "Certificate banner",
                "Certificate badge",
                name="scenario",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.Enum(
                "Load", "Success", "Close", name="action", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scenario_testing_user_id"),
        "scenario_testing",
        ["user_id"],
        unique=False,
    )

    op.add_column(
        "employment",
        sa.Column("certificate_info_snooze_date", sa.Date(), nullable=True),
    )


def downgrade():
    op.drop_column("employment", "certificate_info_snooze_date")

    op.drop_index(
        op.f("ix_scenario_testing_user_id"), table_name="scenario_testing"
    )
    op.drop_table("scenario_testing")
