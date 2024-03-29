"""Add nb_controlled_days in control

Revision ID: b6d1707c5ba1
Revises: 9e2eb44e464d
Create Date: 2022-09-14 12:00:14.770783

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b6d1707c5ba1"
down_revision = "9e2eb44e464d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column("nb_controlled_days", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("controller_control", "nb_controlled_days")
