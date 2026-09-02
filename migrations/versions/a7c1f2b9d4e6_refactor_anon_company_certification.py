"""refactor anon_company_certification to source columns

Revision ID: a7c1f2b9d4e6
Revises: 0da0a33704b0
Create Date: 2026-07-23 15:00:00.000000

The five booleans previously stored on anon_company_certification did not
exist on the source CompanyCertification model, causing AttributeError at
runtime in AnonCompanyCertification.anonymize. Replace them with the four
numeric columns that actually live on CompanyCertification.

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7c1f2b9d4e6"
down_revision = "0da0a33704b0"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("anon_company_certification", "be_active")
    op.drop_column("anon_company_certification", "be_compliant")
    op.drop_column("anon_company_certification", "not_too_many_changes")
    op.drop_column("anon_company_certification", "validate_regularly")
    op.drop_column("anon_company_certification", "log_in_real_time")

    op.add_column(
        "anon_company_certification",
        sa.Column("log_in_real_time", sa.Float(), nullable=False),
    )
    op.add_column(
        "anon_company_certification",
        sa.Column("admin_changes", sa.Float(), nullable=False),
    )
    op.add_column(
        "anon_company_certification",
        sa.Column("compliancy", sa.Integer(), nullable=False),
    )
    op.add_column(
        "anon_company_certification",
        sa.Column("certification_level_int", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_column("anon_company_certification", "certification_level_int")
    op.drop_column("anon_company_certification", "compliancy")
    op.drop_column("anon_company_certification", "admin_changes")
    op.drop_column("anon_company_certification", "log_in_real_time")

    op.add_column(
        "anon_company_certification",
        sa.Column(
            "log_in_real_time",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "anon_company_certification",
        sa.Column(
            "validate_regularly",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "anon_company_certification",
        sa.Column(
            "not_too_many_changes",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "anon_company_certification",
        sa.Column(
            "be_compliant",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "anon_company_certification",
        sa.Column(
            "be_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
