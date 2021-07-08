"""New email

Revision ID: 9d607a1d2b0a
Revises: e9e9adb7e801
Create Date: 2021-07-08 15:09:02.403345

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9d607a1d2b0a"
down_revision = "e9e9adb7e801"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("emailtype", "email")
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


def downgrade():
    op.drop_constraint("emailtype", "email")
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
