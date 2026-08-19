"""add_organizational_unit_contact_table

Revision ID: d89b2d2a3b2c
Revises: 0da0a33704b0
Create Date: 2026-08-19 15:12:38.534524

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d89b2d2a3b2c"
down_revision = "0da0a33704b0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organizational_unit_contact",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column(
            "organizational_unit", sa.String(length=255), nullable=False
        ),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=30), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organizational_unit"),
    )


def downgrade():
    op.drop_table("organizational_unit_contact")
