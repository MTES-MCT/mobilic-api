"""add company stats

Revision ID: 27655467d715
Revises: aa3c6ff8cdb7
Create Date: 2023-08-24 17:09:50.589698

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "27655467d715"
down_revision = "aa3c6ff8cdb7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_stats",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("company_creation_date", sa.Date(), nullable=False),
        sa.Column("first_employee_invitation_date", sa.Date(), nullable=True),
        sa.Column(
            "first_mission_validation_by_admin_date", sa.Date(), nullable=True
        ),
        sa.Column("first_active_criteria_date", sa.Date(), nullable=True),
        sa.Column("first_certification_date", sa.Date(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_company_stats_company_id"),
        "company_stats",
        ["company_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_company_stats_company_creation_date"),
        "company_stats",
        ["company_creation_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_stats_first_active_criteria_date"),
        "company_stats",
        ["first_active_criteria_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_stats_first_certification_date"),
        "company_stats",
        ["first_certification_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_stats_first_employee_invitation_date"),
        "company_stats",
        ["first_employee_invitation_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_stats_first_mission_validation_by_admin_date"),
        "company_stats",
        ["first_mission_validation_by_admin_date"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_company_stats_company_id"), table_name="company_stats"
    )
    op.drop_index(
        op.f("ix_company_stats_first_mission_validation_by_admin_date"),
        table_name="company_stats",
    )
    op.drop_index(
        op.f("ix_company_stats_first_employee_invitation_date"),
        table_name="company_stats",
    )
    op.drop_index(
        op.f("ix_company_stats_first_certification_date"),
        table_name="company_stats",
    )
    op.drop_index(
        op.f("ix_company_stats_first_active_criteria_date"),
        table_name="company_stats",
    )
    op.drop_index(
        op.f("ix_company_stats_company_creation_date"),
        table_name="company_stats",
    )
    op.drop_table("company_stats")
