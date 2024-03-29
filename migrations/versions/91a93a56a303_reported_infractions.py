"""reported infractions

Revision ID: 91a93a56a303
Revises: ecc1e9f03ce8
Create Date: 2023-08-04 11:57:56.944665

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "91a93a56a303"
down_revision = "ecc1e9f03ce8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column(
            "observed_infractions",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "controller_control",
        sa.Column(
            "reported_infractions_last_update_time", sa.DateTime, nullable=True
        ),
    )
    op.add_column(
        "controller_control",
        sa.Column(
            "reported_infractions_first_update_time",
            sa.DateTime,
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "controller_control", "reported_infractions_first_update_time"
    )
    op.drop_column(
        "controller_control", "reported_infractions_last_update_time"
    )
    op.drop_column("controller_control", "observed_infractions")
