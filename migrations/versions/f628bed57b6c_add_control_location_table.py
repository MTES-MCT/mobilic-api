"""add control location table

Revision ID: f628bed57b6c
Revises: 83ea61a446f8
Create Date: 2023-08-02 10:11:55.282557

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f628bed57b6c"
down_revision = "83ea61a446f8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "control_location.py",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("department", sa.String(length=3), nullable=False),
        sa.Column("postal_code", sa.String(length=5), nullable=False),
        sa.Column("commune", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=255), nullable=False),
        sa.Column("greco_code", sa.String(length=255), nullable=False),
        sa.Column("greco_label", sa.String(length=255), nullable=False),
        sa.Column("greco_extra1", sa.String(length=255), nullable=True),
        sa.Column("greco_extra2", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_control_location_department"),
        "control_location.py",
        ["department"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_control_location_department"),
        table_name="control_location.py",
    )
    op.drop_table("control_location.py")
