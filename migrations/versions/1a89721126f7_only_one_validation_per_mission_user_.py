"""Only one validation per mission, user and actor

Revision ID: 1a89721126f7
Revises: fa96dfc8237d
Create Date: 2021-10-14 11:22:01.124488

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1a89721126f7"
down_revision = "fa96dfc8237d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        WITH validation_duplicates AS (
            SELECT
                id,
                ROW_NUMBER() OVER (PARTITION BY user_id, mission_id, submitter_id ORDER BY reception_time DESC) AS rn
            FROM mission_validation
        )
        DELETE FROM mission_validation mv
        USING validation_duplicates vd
        WHERE mv.id = vd.id AND vd.rn >= 2
        """
    )
    op.execute(
        """
        ALTER TABLE mission_validation ADD CONSTRAINT only_one_validation_per_submitter_mission_and_user
        EXCLUDE USING GIST (
            mission_id WITH =,
            submitter_id WITH =,
            user_id WITH =
        )
        """
    )


def downgrade():
    op.drop_constraint(
        "only_one_validation_per_submitter_mission_and_user",
        "mission_validation",
    )
