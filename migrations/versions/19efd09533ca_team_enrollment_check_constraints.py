"""Team enrollment check constraints

Revision ID: 19efd09533ca
Revises: 3030266fdd01
Create Date: 2020-03-19 13:10:21.083895

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "19efd09533ca"
down_revision = "b448927b940a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        "team_enrollment_action_time_before_event_time",
        "team_enrollment",
        "(event_time >= action_time)",
    )
    op.create_check_constraint(
        "team_enrollment_cannot_target_self",
        "team_enrollment",
        "(submitter_id != user_id)",
    )


def downgrade():
    op.drop_constraint(
        "team_enrollment_action_time_before_event_time", "team_enrollment"
    )
    op.drop_constraint("team_enrollment_cannot_target_self", "team_enrollment")
