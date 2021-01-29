"""Add activity id to overlapping_activities_constraint

Revision ID: 13912f58d6e8
Revises: ff7bf9a10e57
Create Date: 2021-01-28 14:38:30.803997

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "13912f58d6e8"
down_revision = "ff7bf9a10e57"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("no_overlapping_acknowledged_activities", "activity")
    op.execute(
        """
        ALTER TABLE activity ADD CONSTRAINT no_overlapping_acknowledged_activities
        EXCLUDE USING GIST (
            user_id WITH =,
            tsrange(start_time, end_time, '[)') WITH &&,
            id WITH <>
        )
        WHERE (dismissed_at is null)
        """
    )


def downgrade():
    op.drop_constraint("no_overlapping_acknowledged_activities", "activity")
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
