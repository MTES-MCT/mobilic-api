"""add phone number to company

Revision ID: c452a761d31a
Revises: bad3fdae2730
Create Date: 2024-06-03 20:54:18.065565

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c452a761d31a"
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
