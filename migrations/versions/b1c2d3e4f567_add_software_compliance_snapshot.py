"""add software compliance snapshot table

Revision ID: b1c2d3e4f567
Revises: 0da0a33704b0
Create Date: 2026-07-30 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f567"
down_revision = "c8f1a2b3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "software_compliance_snapshot",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("client_name", sa.String(), nullable=False),
        sa.Column("nb_missions", sa.Integer(), nullable=False),
        sa.Column("nb_activities", sa.Integer(), nullable=False),
        sa.Column("pct_retroactive_gt4h", sa.Float(), nullable=True),
        sa.Column("pct_retroactive_gt24h", sa.Float(), nullable=True),
        sa.Column("pct_missing_start_loc", sa.Float(), nullable=True),
        sa.Column("pct_missing_end_loc", sa.Float(), nullable=True),
        sa.Column("pct_missing_vehicle", sa.Float(), nullable=True),
        sa.Column("pct_missing_km_start", sa.Float(), nullable=True),
        sa.Column("pct_missing_km_end", sa.Float(), nullable=True),
        sa.Column("pct_auto_validation_only", sa.Float(), nullable=True),
        sa.Column("pct_admin_modified", sa.Float(), nullable=True),
        sa.Column("nb_controls", sa.Integer(), nullable=True),
        sa.Column("pct_controls_with_qr_code", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["oauth2_client.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_date",
            "client_id",
            name="uq_software_compliance_snapshot_date_client",
        ),
    )
    op.create_index(
        op.f("ix_software_compliance_snapshot_snapshot_date"),
        "software_compliance_snapshot",
        ["snapshot_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_software_compliance_snapshot_client_id"),
        "software_compliance_snapshot",
        ["client_id"],
        unique=False,
    )
    op.create_table(
        "software_compliance_alert_state",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("metric", sa.String(), nullable=False),
        sa.Column("last_alerted_on", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["oauth2_client.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_id",
            "metric",
            name="uq_software_compliance_alert_state_client_metric",
        ),
    )
    op.create_index(
        op.f("ix_software_compliance_alert_state_client_id"),
        "software_compliance_alert_state",
        ["client_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_software_compliance_alert_state_client_id"),
        table_name="software_compliance_alert_state",
    )
    op.drop_table("software_compliance_alert_state")
    op.drop_index(
        op.f("ix_software_compliance_snapshot_client_id"),
        table_name="software_compliance_snapshot",
    )
    op.drop_index(
        op.f("ix_software_compliance_snapshot_snapshot_date"),
        table_name="software_compliance_snapshot",
    )
    op.drop_table("software_compliance_snapshot")
