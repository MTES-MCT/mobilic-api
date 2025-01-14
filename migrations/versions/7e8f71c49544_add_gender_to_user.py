"""add gender to user

Revision ID: 7e8f71c49544
Revises: fc7fb77ff350
Create Date: 2025-01-14 13:33:13.918086

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7e8f71c49544"
down_revision = "fc7fb77ff350"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column(
            "gender",
            sa.Enum("female", "male", name="gender", native_enum=False),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("user", "gender")
