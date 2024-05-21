"""add phone number to company

Revision ID: e4237c98388c
Revises: bad3fdae2730
Create Date: 2024-05-21 13:10:41.490218

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e4237c98388c"
down_revision = "bad3fdae2730"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company",
        sa.Column("phone_number", sa.String(length=30), nullable=True),
    )


def downgrade():
    op.drop_column("company", "phone_number")
