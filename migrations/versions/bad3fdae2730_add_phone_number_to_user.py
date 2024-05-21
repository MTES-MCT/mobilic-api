"""add phone number to user

Revision ID: bad3fdae2730
Revises: dab7465f3667
Create Date: 2024-05-13 15:49:17.275162

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bad3fdae2730"
down_revision = "dab7465f3667"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user", sa.Column("phone_number", sa.String(length=30), nullable=True)
    )


def downgrade():
    op.drop_column("user", "phone_number")
