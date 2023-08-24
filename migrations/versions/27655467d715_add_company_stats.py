"""add company stats

Revision ID: 27655467d715
Revises: b93eeb578bdd
Create Date: 2023-08-24 17:09:50.589698

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "27655467d715"
down_revision = "b93eeb578bdd"
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


def downgrade():
    op.drop_index(
        op.f("ix_company_stats_company_id"), table_name="company_stats"
    )
    op.drop_table("company_stats")
