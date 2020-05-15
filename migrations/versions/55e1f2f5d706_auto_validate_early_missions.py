"""auto validate early missions

Revision ID: 55e1f2f5d706
Revises: 020c5cbf1354
Create Date: 2020-05-11 16:39:20.550676

"""
from alembic import op
from sqlalchemy.orm.session import Session
from collections import namedtuple, defaultdict

# revision identifiers, used by Alembic.
revision = "55e1f2f5d706"
down_revision = "020c5cbf1354"
branch_labels = None
depends_on = None


MissionData = namedtuple("MissionData", ["id", "submitter_id"])
ActivityData = namedtuple(
    "ActivityData",
    ["user_id", "mission_id", "user_time", "event_time", "type"],
)


def _auto_validate_missions():
    session = Session(bind=op.get_bind())
    missions = session.execute(
        """
        SELECT id, submitter_id
        FROM mission
        """
    )
    missions = [MissionData(*m) for m in missions]

    activities = session.execute(
        """
        SELECT a.user_id, a.mission_id, a.user_time, a.event_time, a.type
        FROM activity a
        LEFT JOIN activity a2
        ON a2.revisee_id = a.id
        WHERE a.submitter_id = a.user_id AND a.dismiss_type is null AND a2.id is null
        """
    )
    activities = [ActivityData(*a) for a in activities]
    activities_per_mission = defaultdict(list)
    for activity in activities:
        activities_per_mission[activity.mission_id].append(activity)

    for mission in missions:
        sorted_submitter_activities = sorted(
            [
                a
                for a in activities_per_mission[mission.id]
                if a.user_id == mission.submitter_id
            ],
            key=lambda a: a.user_time,
        )
        if (
            sorted_submitter_activities
            and sorted_submitter_activities[-1].type == "rest"
        ):
            latest_event_time = max(
                [a.event_time for a in sorted_submitter_activities]
            )
            session.execute(
                """
                INSERT INTO mission_validation(
                    creation_time,
                    event_time,
                    submitter_id,
                    mission_id
                )
                VALUES(
                    NOW(),
                    :event_time,
                    :submitter_id,
                    :mission_id
                )
                """,
                dict(
                    event_time=latest_event_time,
                    submitter_id=mission.submitter_id,
                    mission_id=mission.id,
                ),
            )


def upgrade():
    _auto_validate_missions()


def downgrade():
    pass
