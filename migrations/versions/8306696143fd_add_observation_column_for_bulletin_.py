"""add observation column for bulletin controle

Revision ID: 8306696143fd
Revises: 0a99a53e565e
Create Date: 2023-05-10 15:21:05.280017

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8306696143fd"
down_revision = "0a99a53e565e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "control_bulletin", sa.Column("observation", sa.TEXT(), nullable=True)
    )


def downgrade():
    op.drop_column("control_bulletin", "observation")
