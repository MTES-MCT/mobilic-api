"""activity start time before event time

Revision ID: f2e6fb409232
Revises: 76530c01c430
Create Date: 2020-03-05 13:49:37.502646

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2e6fb409232"
down_revision = "76530c01c430"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        "activity_start_time_before_event_time",
        "activity",
        "(event_time >= start_time)",
    )


def downgrade():
    op.drop_constraint("activity_start_time_before_event_time", "activity")
