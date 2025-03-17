"""Add anonymized table and temporay id_mapping table

Revision ID: 460f372be359
Revises: fc7fb77ff350
Create Date: 2025-01-12 17:23:15.103538
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.models.user import UserAccountStatus


# revision identifiers, used by Alembic.
revision = "460f372be359"
down_revision = "44bebfc43b10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "temp_id_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("original_id", sa.Integer(), nullable=True),
        sa.Column("anonymized_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type", "original_id", name="uix_entity_original"
        ),
        sa.UniqueConstraint(
            "entity_type", "anonymized_id", name="uix_anon_entity"
        ),
    )
    op.execute(
        """
        CREATE SEQUENCE IF NOT EXISTS anonymized_id_seq
        START WITH 1
        INCREMENT BY 1
        NO MINVALUE
        NO MAXVALUE
        CACHE 1;
    """
    )
    op.create_table(
        "anon_activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=8), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("last_update_time", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_activity_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "anon_mission",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_mission_end",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_mission_validation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_location_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=22), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("address_id", sa.Integer(), nullable=False),
        sa.Column("company_known_address_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_employment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("validation_time", sa.DateTime(), nullable=True),
        sa.Column("validation_status", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("has_admin_rights", sa.Boolean(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("business_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_email",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("type", sa.String(34), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("employment_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_company",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("require_kilometer_data", sa.Boolean(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_anon_company_creation_time",
        "anon_company",
        ["creation_time"],
    )
    op.create_table(
        "anon_user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column(
            "admin", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "has_confirmed_email",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "has_activated_email",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("way_heard_of_mobilic", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_anon_user_creation_time",
        "anon_user",
        ["creation_time"],
    )
    op.create_table(
        "anon_company_certification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("attribution_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("be_active", sa.Boolean(), nullable=False),
        sa.Column("be_compliant", sa.Boolean(), nullable=False),
        sa.Column("not_too_many_changes", sa.Boolean(), nullable=False),
        sa.Column("validate_regularly", sa.Boolean(), nullable=False),
        sa.Column("log_in_real_time", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_company_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("company_creation_date", sa.Date(), nullable=False),
        sa.Column("first_employee_invitation_date", sa.Date(), nullable=True),
        sa.Column(
            "first_mission_validation_by_admin_date", sa.Date(), nullable=True
        ),
        sa.Column("first_active_criteria_date", sa.Date(), nullable=True),
        sa.Column("first_certification_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_vehicle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("terminated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_company_known_address",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("address_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_team",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_team_admin_user",
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("team_id", "user_id"),
    )
    op.create_table(
        "anon_team_known_address",
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("company_known_address_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("team_id", "company_known_address_id"),
    )
    op.execute(
        """
        CREATE INDEX idx_activity_gin ON activity
        USING GIN (
            (ARRAY[user_id, submitter_id, dismiss_author_id])
        ) WITH (fastupdate = on);
    """
    )
    op.create_table(
        "anon_regulatory_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("submitter_type", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("regulation_check_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_regulation_computation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("submitter_type", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_user_agreement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_blacklisted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_controller_control",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("controller_id", sa.Integer(), nullable=False),
        sa.Column("control_type", sa.String(50), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("qr_code_generation_time", sa.DateTime(), nullable=True),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column(
            "control_bulletin_creation_time", sa.DateTime(), nullable=True
        ),
        sa.Column(
            "control_bulletin_first_download_time",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column("observed_infractions", sa.JSON(), nullable=True),
        sa.Column(
            "reported_infractions_last_update_time",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "reported_infractions_first_update_time",
            sa.DateTime(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anon_controller_user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("temp_id_mapping")
    op.execute("DROP SEQUENCE IF EXISTS anonymized_id_seq")
    op.execute("DROP INDEX IF EXISTS idx_activity_gin;")
    op.drop_table("anon_activity_version")
    op.drop_table("anon_activity")
    op.drop_table("anon_mission")
    op.drop_table("anon_mission_end")
    op.drop_table("anon_mission_validation")
    op.drop_table("anon_location_entry")
    op.drop_table("anon_employment")
    op.drop_table("anon_email")
    op.drop_index("ix_anon_company_creation_time")
    op.drop_table("anon_company")
    op.drop_index("ix_anon_user_creation_time")
    op.drop_table("anon_user")
    op.drop_table("anon_company_stats")
    op.drop_table("anon_company_certification")
    op.drop_table("anon_vehicle")
    op.drop_table("anon_company_known_address")
    op.drop_table("anon_team_known_address")
    op.drop_table("anon_team_admin_user")
    op.drop_table("anon_team")
    op.drop_table("anon_user_agreement")
    op.drop_table("anon_regulation_computation")
    op.drop_table("anon_regulatory_alert")
    op.drop_table("anon_controller_control")
    op.drop_table("anon_controller_user")
