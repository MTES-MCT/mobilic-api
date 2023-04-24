"""add certification communication boolean

Revision ID: 90acbc440024
Revises: c98854a361af
Create Date: 2023-04-18 16:04:32.434147

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "90acbc440024"
down_revision = "c98854a361af"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company",
        sa.Column(
            "accept_certification_communication", sa.Boolean(), nullable=True
        ),
    )
    op.alter_column(
        "company_certification",
        "expiration_date",
        existing_type=sa.DATE(),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "company_certification",
        "expiration_date",
        existing_type=sa.DATE(),
        nullable=True,
    )
    op.drop_column("company", "accept_certification_communication")
    # ### end Alembic commands ###
