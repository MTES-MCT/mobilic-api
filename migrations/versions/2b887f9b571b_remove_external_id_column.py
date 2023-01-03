"""remove external id column

Revision ID: 2b887f9b571b
Revises: b5afcd504879
Create Date: 2023-01-03 12:05:09.175856

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2b887f9b571b"
down_revision = "b5afcd504879"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("employment", "external_id")


def downgrade():
    op.add_column(
        "employment",
        sa.Column(
            "external_id",
            sa.VARCHAR(length=255),
            autoincrement=False,
            nullable=True,
        ),
    )
