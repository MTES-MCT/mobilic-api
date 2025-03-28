"""company cease activity

Revision ID: 15fc3b5f23c4
Revises: 460f372be359
Create Date: 2025-03-21 09:49:28.618069

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "15fc3b5f23c4"
down_revision = "460f372be359"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company",
        sa.Column(
            "has_ceased_activity", sa.Boolean(), nullable=True, default=False
        ),
    )
    op.execute(
        "UPDATE company SET has_ceased_activity = FALSE WHERE has_ceased_activity IS NULL"
    )
    op.alter_column("company", "has_ceased_activity", nullable=False)

    op.add_column(
        "company",
        sa.Column(
            "siren_api_info_last_update",
            sa.Date(),
            nullable=True,
            default=sa.func.current_date(),
        ),
    )

    op.create_index(
        "ix_company_siren_api_info_last_update",
        "company",
        ["siren_api_info_last_update"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_company_siren_api_info_last_update", table_name="company"
    )
    op.drop_column("company", "has_ceased_activity")
    op.drop_column("company", "siren_api_info_last_update")
