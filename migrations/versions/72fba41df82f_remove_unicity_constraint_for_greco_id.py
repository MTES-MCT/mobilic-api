"""remove unicity constraint for greco id

Revision ID: 72fba41df82f
Revises: 83ea61a446f8
Create Date: 2023-08-03 10:47:32.922605

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "72fba41df82f"
down_revision = "83ea61a446f8"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "controller_user_greco_id_key", "controller_user", type_="unique"
    )


def downgrade():
    op.create_unique_constraint(
        "controller_user_greco_id_key", "controller_user", ["greco_id"]
    )
