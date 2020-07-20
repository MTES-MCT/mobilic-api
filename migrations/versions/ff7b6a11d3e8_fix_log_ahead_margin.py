"""Fix log-ahead margin

Revision ID: ff7b6a11d3e8
Revises: 749ceabbea95
Create Date: 2020-07-20 15:03:51.238357

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ff7b6a11d3e8"
down_revision = "16ff1e79bfad"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("activity_start_time_before_reception_time", "activity")
    op.create_check_constraint(
        "activity_start_time_before_reception_time",
        "activity",
        "(reception_time + interval '300 seconds' >= start_time)",
    )


def downgrade():
    op.drop_constraint("activity_start_time_before_reception_time", "activity")
    op.create_check_constraint(
        "activity_start_time_before_reception_time",
        "activity",
        "(reception_time >= start_time)",
    )
