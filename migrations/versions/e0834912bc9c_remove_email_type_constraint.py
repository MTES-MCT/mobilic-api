"""remove email type constraint

Revision ID: e0834912bc9c
Revises: 80dfc91bbd27
Create Date: 2023-01-18 17:24:31.747795

"""
from alembic import op
import sqlalchemy as sa


revision = "e0834912bc9c"
down_revision = "80dfc91bbd27"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("emailtype", "email")


def downgrade():
    op.alter_column(
        "email",
        "type",
        type_=sa.Enum(
            "account_activation",
            "company_creation",
            "employment_validation_confirmation",
            "invitation",
            "mission_changes_warning",
            "new_mission_information",
            "reset_password",
            "worker_onboarding_first_info",
            "worker_onboarding_second_info",
            "manager_onboarding_first_info",
            "manager_onboarding_second_info",
            name="emailtype",
            native_enum=False,
        ),
        nullable=False,
    )
