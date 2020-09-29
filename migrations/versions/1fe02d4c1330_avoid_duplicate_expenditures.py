"""avoid duplicate expenditures

Revision ID: 1fe02d4c1330
Revises: af395b68485a
Create Date: 2020-09-28 10:51:29.771808

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1fe02d4c1330"
down_revision = "af395b68485a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE expenditure ADD CONSTRAINT no_duplicate_expenditures_per_user_and_mission
        EXCLUDE USING GIST (
            user_id WITH =,
            mission_id WITH =,
            type WITH =
        )
        WHERE (dismissed_at is null)
        """
    )


def downgrade():
    op.drop_constraint(
        "no_duplicate_expenditures_per_user_and_mission", "expenditure"
    )
