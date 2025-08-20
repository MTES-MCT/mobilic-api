"""certificate rework model

Revision ID: 022d979043d0
Revises: 68ed4db9ae15
Create Date: 2025-07-30 10:12:10.850163

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from migrations.versions.c98854a361af_add_company_certification_table import (
    create_original_company_certification_table,
)

# revision identifiers, used by Alembic.
revision = "022d979043d0"
down_revision = "68ed4db9ae15"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(
        op.f("ix_company_certification_company_id"),
        table_name="company_certification",
    )
    op.drop_table("company_certification")
    op.create_table(
        "company_certification",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("attribution_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("log_in_real_time", sa.Float(), nullable=False),
        sa.Column("admin_changes", sa.Float(), nullable=False),
        sa.Column("compliancy", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "info",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_company_certification_company_id"),
        "company_certification",
        ["company_id"],
        unique=False,
    )


def downgrade():
    # Restore original company certification table
    op.drop_index(
        op.f("ix_company_certification_company_id"),
        table_name="company_certification",
    )
    op.drop_table("company_certification")
    create_original_company_certification_table()
