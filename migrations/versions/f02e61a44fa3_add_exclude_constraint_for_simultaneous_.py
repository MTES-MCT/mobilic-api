"""add exclude constraint for simultaneous activities

Revision ID: f02e61a44fa3
Revises: 17a9939344be
Create Date: 2020-08-12 17:27:59.828238

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f02e61a44fa3"
down_revision = "17a9939344be"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE activity ADD CONSTRAINT no_simultaneous_acknowledged_activities
        EXCLUDE USING GIST (
            start_time WITH =,
            user_id WITH =
        )
        WHERE (dismissed_at is null AND revised_by_id is null)
        """
    )


def downgrade():
    op.drop_constraint("no_simultaneous_acknowledged_activities", "activity")
