"""add technical_incident table

Revision ID: b1e7c9a2f4d3
Revises: e5d78113a5ac
Create Date: 2026-09-12 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b1e7c9a2f4d3"
down_revision = "e5d78113a5ac"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "technical_incident",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column(
            "technical_type",
            sa.Enum(
                "server_down",
                "dns_switch",
                "ssl_expired",
                "database_down",
                "backend_api_unavailable",
                "slowdown_timeout",
                "deploy_regression",
                "time_entry_bug",
                "offline_sync_bug",
                "auth_outage",
                "email_unavailable",
                "third_party_outage",
                "planned_maintenance",
                name="technicalincidenttype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_technical_incident_start_time"),
        "technical_incident",
        ["start_time"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_technical_incident_start_time"),
        table_name="technical_incident",
    )
    op.drop_table("technical_incident")
