"""add number of workers field in company

Revision ID: 60d7e99b85f3
Revises: bd0cdf9f16bd
Create Date: 2025-01-03 15:14:15.786699

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "60d7e99b85f3"
down_revision = "bd0cdf9f16bd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company", sa.Column("number_workers", sa.Integer(), nullable=True)
    )


def downgrade():
    op.drop_column("company", "number_workers")
