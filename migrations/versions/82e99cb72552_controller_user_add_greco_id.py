"""controller_user add greco id

Revision ID: 82e99cb72552
Revises: 8306696143fd
Create Date: 2023-05-26 11:17:08.026151

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "82e99cb72552"
down_revision = "8306696143fd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_user",
        sa.Column("greco_id", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(None, "controller_user", ["greco_id"])


def downgrade():
    op.drop_constraint(None, "controller_user", type_="unique")
    op.drop_column("controller_user", "greco_id")
