"""drop identifying columns from anon tables (privacy hardening step 2)

Revision ID: b9c8a1d2e3f4
Revises: e1f2a3b4c5d6
Create Date: 2026-08-06 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b9c8a1d2e3f4"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("anon_mission_validation", "is_admin")
    op.drop_column("anon_employment", "has_admin_rights")
    op.drop_column("anon_regulatory_alert", "regulation_check_id")


def downgrade():
    op.add_column(
        "anon_regulatory_alert",
        sa.Column("regulation_check_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "anon_employment",
        sa.Column("has_admin_rights", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "anon_mission_validation",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
