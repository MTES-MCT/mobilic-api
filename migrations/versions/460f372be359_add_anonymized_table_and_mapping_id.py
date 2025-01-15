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
down_revision = "fc7fb77ff350"
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
            "entity_type", "anonymized_id", name="uix_entity_anonymized"
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
        "activity_anonymized",
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
        "activity_version_anonymized",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("reception_time", sa.DateTime(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mission_anonymized",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("reception_time", sa.DateTime(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "company_anonymized",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("allow_team_mode", sa.Boolean(), nullable=False),
        sa.Column("require_kilometer_data", sa.Boolean(), nullable=False),
        sa.Column("require_expenditures", sa.Boolean(), nullable=False),
        sa.Column("require_support_activity", sa.Boolean(), nullable=False),
        sa.Column("require_mission_name", sa.Boolean(), nullable=False),
        sa.Column("allow_transfers", sa.Boolean(), nullable=False),
        sa.Column(
            "accept_certification_communication", sa.Boolean(), nullable=True
        ),
        sa.Column("business_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["business.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mission_end_anonymized",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("reception_time", sa.DateTime(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mission_validation_anonymized",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("reception_time", sa.DateTime(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "location_entry_anonymized",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=22), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("address_id", sa.Integer(), nullable=False),
        sa.Column("company_known_address_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "employment_anonymized",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("validation_time", sa.DateTime(), nullable=True),
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
        "email_anonymized",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("type", sa.String(34), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("employment_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user_anonymized",
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
        sa.Column(
            "status",
            postgresql.ENUM(
                UserAccountStatus,
                name="user_account_status",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_anonymized_creation_time",
        "user_anonymized",
        ["creation_time"],
    )


def downgrade():
    op.drop_table("temp_id_mapping")
    op.execute("DROP SEQUENCE IF EXISTS anonymized_id_seq")
    op.drop_table("activity_version_anonymized")
    op.drop_table("activity_anonymized")
    op.drop_table("mission_anonymized")
    op.drop_table("company_anonymized")
    op.drop_table("mission_end_anonymized")
    op.drop_table("mission_validation_anonymized")
    op.drop_table("location_entry_anonymized")
    op.drop_table("employment_anonymized")
    op.drop_table("email_anonymized")
    op.drop_index("ix_user_anonymized_creation_time")
    op.drop_table("user_anonymized")
