"""add_email_to_organizational_unit_contact

Revision ID: 67d7cbf16078
Revises: d89b2d2a3b2c
Create Date: 2026-10-27 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "67d7cbf16078"
down_revision = "d89b2d2a3b2c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizational_unit_contact",
        sa.Column("email", sa.String(length=255), nullable=True),
    )


def downgrade():
    op.drop_column("organizational_unit_contact", "email")
