"""Deffered overlapping activities constraint

Revision ID: 420dbfec0b28
Revises: bc7abe3eb83c
Create Date: 2022-06-09 10:19:59.480830

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "420dbfec0b28"
down_revision = "320dbbdd0b27"
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
        DEFERRABLE INITIALLY DEFERRED 
        """
    )


def downgrade():
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
