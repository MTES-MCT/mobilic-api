"""add business in regulatory alert

Revision ID: 83a221435ceb
Revises: bd643a8d5269
Create Date: 2024-11-06 14:01:58.678276

"""
from alembic import op
import sqlalchemy as sa

from app.domain.regulations import get_default_business

# revision identifiers, used by Alembic.
revision = "83a221435ceb"
down_revision = "bd643a8d5269"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "regulatory_alert",
        sa.Column("business_id", sa.Integer(), nullable=True),
    )

    default_business = get_default_business()
    connection = (
        op.get_bind()
    )  # Get the database connection from Alembic's operation context
    connection.execute(
        sa.text(
            "UPDATE regulatory_alert SET business_id = :business_id WHERE business_id IS NULL"
        ),
        {"business_id": default_business.id},
    )

    op.create_foreign_key(
        None, "regulatory_alert", "business", ["business_id"], ["id"]
    )
    op.alter_column("regulatory_alert", "business_id", nullable=False)


def downgrade():
    op.drop_column("regulatory_alert", "business_id")
