"""Remove seconds from start and end times

Revision ID: 15bacad268d4
Revises: e920e737ca5a
Create Date: 2020-10-26 11:41:00.746550

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "15bacad268d4"
down_revision = "e920e737ca5a"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("activity_start_time_before_end_time", "activity")
    op.create_check_constraint(
        "activity_start_time_before_end_time",
        "activity",
        "(end_time is null or start_time <= end_time)",
    )
    op.drop_constraint(
        "activity_version_start_time_before_end_time", "activity_version"
    )
    op.create_check_constraint(
        "activity_version_start_time_before_end_time",
        "activity_version",
        "(end_time is null or start_time <= end_time)",
    )

    op.drop_constraint("no_sucessive_activities_with_same_type", "activity")
    op.execute(
        """
        ALTER TABLE activity ADD CONSTRAINT no_sucessive_activities_with_same_type
        CHECK (1 = 1)
        """
    )
    op.drop_constraint("no_overlapping_acknowledged_activities", "activity")
    op.execute(
        """
        UPDATE activity SET start_time = date_trunc('minute', start_time), end_time = date_trunc('minute', end_time)
    """
    )
    op.execute(
        """
            UPDATE activity_version SET start_time = date_trunc('minute', start_time), end_time = date_trunc('minute', end_time)
        """
    )
    op.execute(
        """
        ALTER TABLE activity ADD CONSTRAINT no_overlapping_acknowledged_activities
        EXCLUDE USING GIST (
            user_id WITH =,
            tsrange(start_time, end_time, '[)') WITH &&
        )
        WHERE (dismissed_at is null)
        """
    )
    op.drop_column("employment", "dismiss_received_at")
    op.drop_column("expenditure", "dismiss_received_at")
    # ### end Alembic commands ###


def downgrade():
    pass
