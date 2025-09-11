"""remove certification communication boolean

Revision ID: 349352e8308d
Revises: bde869cbd775
Create Date: 2025-09-11 16:53:26.672406

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "349352e8308d"
down_revision = "bde869cbd775"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("company", "accept_certification_communication")


def downgrade():
    op.alter_column(
        "company",
        "siren_api_info_last_update",
        existing_type=sa.DATE(),
        nullable=True,
    )
