"""Add mission end id to existing mission end constraint

Revision ID: 75b8081a1c9c
Revises: 13912f58d6e8
Create Date: 2021-01-28 15:31:49.307000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "75b8081a1c9c"
down_revision = "13912f58d6e8"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("user_can_only_end_mission_once", "mission_end")
    op.execute(
        """
        ALTER TABLE mission_end ADD CONSTRAINT user_can_only_end_mission_once
        EXCLUDE USING GIST (
            mission_id WITH =,
            user_id WITH =,
            id WITH <>
        )
        """
    )


def downgrade():
    op.drop_constraint("user_can_only_end_mission_once", "mission_end")
    op.create_unique_constraint(
        "user_can_only_end_mission_once",
        "mission_end",
        ["mission_id", "user_id"],
    )
