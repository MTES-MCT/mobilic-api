"""Revamp mission model

Revision ID: 1648f72277eb
Revises: bbacbf6d536b
Create Date: 2020-04-24 13:08:18.120598

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.session import Session
from collections import namedtuple, defaultdict
import json

revision = "1648f72277eb"
down_revision = "bbacbf6d536b"
branch_labels = None
depends_on = None

MissionData = namedtuple("MissionData", ["submitter_id", "event_time", "name"])
ActivityData = namedtuple(
    "ActivityData", ["id", "submitter_id", "user_time", "type", "user_id"]
)
ExpenditureData = namedtuple(
    "ExpenditureData", ["submitter_id", "type", "event_time"]
)


def _migrate_missions():
    session = Session(bind=op.get_bind())
    activities = session.execute(
        """
        SELECT a.id, a.submitter_id, a.user_time, a.type, a.user_id
        FROM activity a
        LEFT JOIN activity a2
        ON a2.revisee_id = a.id
        WHERE a.submitter_id = a.user_id AND a.dismiss_type is null AND a2.id is null
        """
    )
    activities = sorted(
        [ActivityData(*a) for a in activities], key=lambda a: a.user_time
    )
    activities_per_submitter = defaultdict(list)
    for activity in activities:
        activities_per_submitter[activity.submitter_id].append(activity)

    missions = session.execute(
        """
        SELECT submitter_id, event_time, name
        FROM mission
        """
    )
    missions = sorted(
        [MissionData(*m) for m in missions], key=lambda m: m.event_time
    )
    missions_per_submitter = defaultdict(list)
    for mission in missions:
        missions_per_submitter[mission.submitter_id].append(mission)

    expenditures = session.execute(
        """
        SELECT submitter_id, type, event_time
        FROM expenditure
        WHERE submitter_id = user_id
        AND dismiss_type is null
        """
    )
    expenditures = sorted(
        [ExpenditureData(*e) for e in expenditures], key=lambda e: e.event_time
    )
    expenditures_per_submitter = defaultdict(list)
    for expenditure in expenditures:
        expenditures_per_submitter[expenditure.submitter_id].append(
            expenditure
        )

    session.execute("DELETE FROM mission")
    op.alter_column("mission", "name", nullable=True)
    op.add_column(
        "mission",
        sa.Column(
            "expenditures",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )

    missions_to_create = defaultdict(list)
    # First create the missions from groups of activities. Activitis are grouped thus :
    # - same submitter
    # - each rest activity marks the end of a group (= the end of the mission)
    for submitter_id, activities in activities_per_submitter.items():
        current_mission_to_create = None
        current_mission_is_ended = False
        relevant_missions = missions_per_submitter.get(submitter_id, [])
        for activity in activities:
            missions_in_db = [
                m
                for m in relevant_missions
                if m.event_time <= activity.user_time
            ]
            activity_mission_name = (
                missions_in_db[-1].name if missions_in_db else None
            )
            if not current_mission_to_create or current_mission_is_ended:
                new_mission_to_create = MissionData(
                    submitter_id=submitter_id,
                    event_time=activity.user_time,
                    name=activity_mission_name,
                )
                missions_to_create[submitter_id].append(new_mission_to_create)
                current_mission_to_create = new_mission_to_create
                current_mission_is_ended = False
            if activity.type == "rest":
                current_mission_is_ended = True
                relevant_missions = [
                    m
                    for m in relevant_missions
                    if m.event_time > activity.user_time
                ]

    # Now write the newly created missions to the DB
    for submitter_id, missions in missions_to_create.items():
        for (mission, next_mission) in zip(missions, missions[1:] + [None]):
            # Associate to the mission any expenditure submitted (by the same submitter) between this mission "start" time and the next
            time_range_for_expenditures = (
                mission.event_time,
                next_mission.event_time
                if next_mission
                else datetime(2100, 1, 1),
            )
            mission_expenditures = [
                e
                for e in expenditures_per_submitter[submitter_id]
                if time_range_for_expenditures[0]
                <= e.event_time
                <= time_range_for_expenditures[1]
            ]
            expenditure_field = defaultdict(lambda: 0)
            for e in mission_expenditures:
                expenditure_field[e.type] += 1
            session.execute(
                """
                INSERT INTO mission(
                    creation_time,
                    name,
                    event_time,
                    submitter_id,
                    expenditures
                )
                VALUES(
                    NOW(),
                    :name,
                    :event_time,
                    :submitter_id,
                    :expenditures
                )
                """,
                dict(
                    submitter_id=submitter_id,
                    event_time=mission.event_time,
                    name=mission.name,
                    expenditures=json.dumps(dict(expenditure_field)),
                ),
            )

    op.add_column(
        "activity", sa.Column("mission_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_activity_mission_id"),
        "activity",
        ["mission_id"],
        unique=False,
    )
    op.create_foreign_key(None, "activity", "mission", ["mission_id"], ["id"])

    # Link the activities to the missions

    ## 1 Join activities and missions based on the submitter
    session.execute(
        """
        CREATE TEMP TABLE activity_joined_with_mission AS (
            SELECT 
                a.id,
                m.id as mission_id,
                (m.event_time <= a.user_time) AS mission_already_started,
                ROW_NUMBER() OVER (PARTITION BY a.id, (m.event_time <= a.user_time) ORDER BY m.event_time DESC) AS rn1,
                ROW_NUMBER() OVER (PARTITION BY a.id ORDER BY m.event_time) AS rn2
            FROM activity a
            JOIN mission m
            ON a.submitter_id = m.submitter_id
        )
        """
    )

    ## 2. Find the current mission at activity time
    session.execute(
        """
        UPDATE activity a SET mission_id = ajwm.mission_id
        FROM activity_joined_with_mission ajwm
        WHERE a.id = ajwm.id 
        AND ajwm.rn1 = 1
        AND ajwm.mission_already_started
        """
    )
    ## 3. Fallback if there was no active mission at activity time
    session.execute(
        """
        UPDATE activity a SET mission_id = ajwm.mission_id
        FROM activity_joined_with_mission ajwm
        WHERE a.mission_id is null
        AND a.id = ajwm.id 
        AND ajwm.rn2 = 1
        """
    )
    op.alter_column("activity", "mission_id", nullable=False)

    op.add_column(
        "vehicle_booking", sa.Column("mission_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_vehicle_booking_mission_id"),
        "vehicle_booking",
        ["mission_id"],
        unique=False,
    )
    op.create_foreign_key(
        None, "vehicle_booking", "mission", ["mission_id"], ["id"]
    )

    # Link the vehicle bookings to the missions as well
    session.execute(
        """
        CREATE TEMP TABLE vehicle_booking_joined_with_mission AS (
            SELECT 
                vb.id,
                m.id as mission_id,
                (m.event_time <= vb.user_time) AS mission_already_started,
                ROW_NUMBER() OVER (PARTITION BY vb.id, (m.event_time <= vb.user_time)  ORDER BY m.event_time DESC) AS rn1,
                ROW_NUMBER() OVER (PARTITION BY vb.id ORDER BY m.event_time) AS rn2
            FROM vehicle_booking vb
            JOIN mission m
            ON vb.submitter_id = m.submitter_id
        )
        """
    )

    ## 2. Find the current mission at activity time
    session.execute(
        """
        UPDATE vehicle_booking vb SET mission_id = vbjwm.mission_id
        FROM vehicle_booking_joined_with_mission vbjwm
        WHERE vb.mission_id is null
        AND vb.id = vbjwm.id 
        AND vbjwm.rn2 = 1
        """
    )
    ## 3. Fallback if there was no active mission at activity time
    session.execute(
        """
        UPDATE vehicle_booking vb SET mission_id = vbjwm.mission_id
        FROM vehicle_booking_joined_with_mission vbjwm
        WHERE vb.id = vbjwm.id 
        AND vbjwm.rn1 = 1
        AND vbjwm.mission_already_started
        """
    )
    op.alter_column("vehicle_booking", "mission_id", nullable=False)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("activitydismisstype", "activity")
    op.alter_column(
        "activity",
        "dismiss_type",
        type_=sa.Enum(
            "no_activity_switch",
            "user_cancel",
            "break_or_rest_as_starting_activity",
            name="activitydismisstype",
            native_enum=False,
        ),
        nullable=True,
    )

    _migrate_missions()


def downgrade():
    op.drop_constraint("activitydismisstype", "activity")
    op.alter_column(
        "activity",
        "dismiss_type",
        type_=sa.Enum(
            "no_activity_switch",
            "user_cancel",
            "unauthorized_submitter",
            name="activitydismisstype",
            native_enum=False,
        ),
        nullable=True,
    )

    op.drop_constraint(None, "vehicle_booking", type_="foreignkey")
    op.drop_index(
        op.f("ix_vehicle_booking_mission_id"), table_name="vehicle_booking"
    )
    op.drop_column("vehicle_booking", "mission_id")
    op.drop_column("mission", "expenditures")
    op.drop_constraint(None, "activity", type_="foreignkey")
    op.drop_index(op.f("ix_activity_mission_id"), table_name="activity")
    op.drop_column("activity", "mission_id")
    # ### end Alembic commands ###
