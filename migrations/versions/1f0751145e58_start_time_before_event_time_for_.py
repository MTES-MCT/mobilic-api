"""start time before event time for mission and vehicle

Revision ID: 1f0751145e58
Revises: 5f353286ae5b
Create Date: 2020-03-24 18:46:52.213475

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1f0751145e58"
down_revision = "5f353286ae5b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        "vehicle_booking_start_time_before_event_time",
        "vehicle_booking",
        "(event_time >= start_time)",
    )
    op.create_check_constraint(
        "mission_start_time_before_event_time",
        "mission",
        "(event_time >= start_time)",
    )


def downgrade():
    op.drop_constraint("mission_start_time_before_event_time", "mission")
    op.drop_constraint(
        "vehicle_booking_start_time_before_event_time", "vehicle_booking"
    )
