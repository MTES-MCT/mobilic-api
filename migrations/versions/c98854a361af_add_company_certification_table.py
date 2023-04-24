"""add company certification table

Revision ID: c98854a361af
Revises: 930314f0ed57
Create Date: 2023-03-27 12:06:02.479776

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c98854a361af"
down_revision = "930314f0ed57"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_certification",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("attribution_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("be_active", sa.Boolean(), nullable=False),
        sa.Column("be_compliant", sa.Boolean(), nullable=False),
        sa.Column("not_too_many_changes", sa.Boolean(), nullable=False),
        sa.Column("validate_regularly", sa.Boolean(), nullable=False),
        sa.Column("log_in_real_time", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
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
    op.drop_index(
        op.f("ix_company_certification_company_id"),
        table_name="company_certification",
    )
    op.drop_table("company_certification")
