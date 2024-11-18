"""add day page filled in control

Revision ID: 06188fcde16b
Revises: 83a221435ceb
Create Date: 2024-10-28 19:04:03.717178

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "06188fcde16b"
down_revision = "83a221435ceb"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column("is_day_page_filled", sa.Boolean(), nullable=True),
    )


def downgrade():
    op.drop_column("controller_control", "is_day_page_filled")
