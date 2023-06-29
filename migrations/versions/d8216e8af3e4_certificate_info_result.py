"""certificate info result

Revision ID: d8216e8af3e4
Revises: d342aeb2a88f
Create Date: 2023-06-28 09:49:28.275367

"""
from alembic import op
import sqlalchemy as sa

import app

# revision identifiers, used by Alembic.
revision = "d8216e8af3e4"
down_revision = "d342aeb2a88f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "certificate_info_result",
        sa.Column(
            "creation_time",
            app.helpers.db.DateTimeStoredAsUTC(),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "scenario",
            sa.Enum(
                "Scenario A",
                "Scenario B",
                name="certificateinfoscenario",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.Enum(
                "Load",
                "Success",
                "Close",
                name="certificateinfoaction",
                native_enum=False,
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
        op.f("ix_certificate_info_result_user_id"),
        "certificate_info_result",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_certificate_info_result_user_id"),
        table_name="certificate_info_result",
    )
    op.drop_table("certificate_info_result")
