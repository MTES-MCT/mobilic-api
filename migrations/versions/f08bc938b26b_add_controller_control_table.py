"""add controller control table

Revision ID: f08bc938b26b
Revises: b29f8f5e455b
Create Date: 2022-08-11 16:26:33.678499

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f08bc938b26b"
down_revision = "b29f8f5e455b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "controller_control",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("controller_id", sa.Integer(), nullable=False),
        sa.Column(
            "control_type",
            sa.Enum("mobilic", "lic_papier", "sans_lic", name="controltype"),
            nullable=True,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["controller_id"],
            ["controller_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_controller_control_controller_id"),
        "controller_control",
        ["controller_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_controller_control_user_id"),
        "controller_control",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_controller_control_user_id"), table_name="controller_control"
    )
    op.drop_index(
        op.f("ix_controller_control_controller_id"),
        table_name="controller_control",
    )
    op.drop_table("controller_control")
