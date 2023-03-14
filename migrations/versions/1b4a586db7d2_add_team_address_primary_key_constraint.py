"""Add team address primary key constraint

Revision ID: 1b4a586db7d2
Revises: 07b7dba42f71
Create Date: 2023-03-02 17:30:12.269449

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1b4a586db7d2"
down_revision = "07b7dba42f71"
branch_labels = None
depends_on = None


def upgrade():
    op.create_primary_key(
        "team_known_address_pkey",
        "team_known_address",
        ["team_id", "company_known_address_id"],
    )


def downgrade():
    op.drop_constraint(
        "team_known_address_pkey", "team_known_address", type_="primary"
    )
