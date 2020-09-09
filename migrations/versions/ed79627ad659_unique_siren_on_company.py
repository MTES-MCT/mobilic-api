"""Unique SIREN on company

Revision ID: ed79627ad659
Revises: 376542d9939a
Create Date: 2020-09-08 11:35:01.848681

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ed79627ad659"
down_revision = "376542d9939a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("company_siren_key", "company", ["siren"], unique=True)


def downgrade():
    op.drop_index("company_siren_key", "company")
