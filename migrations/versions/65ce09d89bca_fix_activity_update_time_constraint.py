"""fix activity update time constraint

Revision ID: 65ce09d89bca
Revises: 15bacad268d4
Create Date: 2020-10-26 13:08:26.699632

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "65ce09d89bca"
down_revision = "15bacad268d4"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("activity_start_time_before_reception_time", "activity")
    op.create_check_constraint(
        "activity_start_time_before_update_time",
        "activity",
        "(last_update_time + interval '300 seconds' >= start_time)",
    )


def downgrade():
    pass
