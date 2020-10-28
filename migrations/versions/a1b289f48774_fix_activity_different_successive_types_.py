"""fix_activity_different_successive_types_constraint

Revision ID: a1b289f48774
Revises: 65ce09d89bca
Create Date: 2020-10-27 13:21:51.891561

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b289f48774"
down_revision = "65ce09d89bca"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("no_sucessive_activities_with_same_type", "activity")
    op.execute(
        """
        ALTER TABLE activity ADD CONSTRAINT no_sucessive_activities_with_same_type
        EXCLUDE USING GIST (
            user_id WITH =,
            type WITH =,
            tsrange(start_time, end_time, '[)') WITH -|-
        )
        WHERE (dismissed_at is null and (end_time is null or start_time < end_time))
        """
    )
