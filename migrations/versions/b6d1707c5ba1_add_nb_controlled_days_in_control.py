"""Add nb_controlled_days in control

Revision ID: b6d1707c5ba1
Revises: ec4e193da96a
Create Date: 2022-09-14 12:00:14.770783

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b6d1707c5ba1"
down_revision = "ec4e193da96a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column("nb_controlled_days", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("controller_control", "nb_controlled_days")
