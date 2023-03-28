"""Rename known address column in association table 

Revision ID: 07b7dba42f71
Revises: a482261c5eb9
Create Date: 2023-02-16 13:54:08.211996

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "07b7dba42f71"
down_revision = "a482261c5eb9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "team_known_address",
        sa.Column("company_known_address_id", sa.Integer(), nullable=False),
    )
    op.drop_constraint(
        "team_known_address_address_id_fkey",
        "team_known_address",
        type_="foreignkey",
    )
    op.create_foreign_key(
        None,
        "team_known_address",
        "company_known_address",
        ["company_known_address_id"],
        ["id"],
    )
    op.drop_column("team_known_address", "address_id")


def downgrade():
    op.add_column(
        "team_known_address",
        sa.Column(
            "address_id", sa.INTEGER(), autoincrement=False, nullable=False
        ),
    )
    op.drop_constraint(None, "team_known_address", type_="foreignkey")
    op.create_foreign_key(
        "team_known_address_address_id_fkey",
        "team_known_address",
        "company_known_address",
        ["address_id"],
        ["id"],
    )
    op.drop_column("team_known_address", "company_known_address_id")
