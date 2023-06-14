"""create control bulletin table

Revision ID: 32ba9730e22c
Revises: 90acbc440024
Create Date: 2023-04-27 17:08:41.846250

"""
from alembic import op
import sqlalchemy as sa

from app import app

# revision identifiers, used by Alembic.
revision = "32ba9730e22c"
down_revision = "90acbc440024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "control_bulletin",
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("user_first_name", sa.String(length=255), nullable=True),
        sa.Column("user_last_name", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["controller_control.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_control_bulletin_control_id"),
        "control_bulletin",
        ["control_id"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        op.f("ix_control_bulletin_control_id"), table_name="control_bulletin"
    )
    op.drop_table("control_bulletin")
