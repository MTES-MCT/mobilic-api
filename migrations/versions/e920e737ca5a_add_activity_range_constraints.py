"""Add activity range constraints

Revision ID: e920e737ca5a
Revises: 5bad2b03c508
Create Date: 2020-10-18 21:38:12.563914

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from collections import defaultdict
from sqlalchemy.orm import Session
from types import SimpleNamespace
import json

# revision identifiers, used by Alembic.
revision = "e920e737ca5a"
down_revision = "5bad2b03c508"
branch_labels = None
depends_on = None


class _SimpleNamespace(SimpleNamespace):
    def __hash__(self):
        return self.id


ActivityData = _SimpleNamespace
ActivityEvent = _SimpleNamespace

RevisionData = _SimpleNamespace


def _migrate_activities():
    session = Session(bind=op.get_bind())
    activities = session.execute(
        """
        SELECT a.id, a.submitter_id, a.start_time, a.reception_time, a.type, a.dismissed_at, a.dismiss_type, a.dismiss_author_id, a.dismiss_context, a.user_id, a2.id as revisee_id, a.mission_id, a.context
        FROM activity a
        LEFT JOIN activity a2
        ON a.id = a2.revised_by_id
        ORDER BY a.reception_time
        """
    )
    activities = [ActivityData(**a, end_time=None) for a in activities]

    user_mission_activities = defaultdict(lambda: defaultdict(list))
    for _activity in activities:
        user_mission_activities[_activity.user_id][
            _activity.mission_id
        ].append(_activity)

    for user_id, missions in user_mission_activities.items():
        for mission_id, acts in missions.items():
            activity_events_by_reception_time = defaultdict(list)
            activities_by_reception_time = [
                (
                    a.reception_time,
                    ActivityEvent(
                        type="revision" if a.revisee_id else "log", activity=a
                    ),
                )
                for a in acts
            ]
            dismisses_by_reception_time = [
                (
                    a.dismissed_at,
                    ActivityEvent(type=a.dismiss_type, activity=a),
                )
                for a in acts
                if a.dismissed_at
            ]

            activities_and_dismisses_by_reception_time = sorted(
                activities_by_reception_time + dismisses_by_reception_time,
                key=lambda act_tuple: act_tuple[0],
            )
            for a in activities_and_dismisses_by_reception_time:
                activity_events_by_reception_time[a[0]].append(a[1])

            current_valid_activities = set()
            activities_to_keep = defaultdict(dict)
            all_mission_activities_for_user = [
                a.id
                for a in session.execute(
                    """
                SELECT id from activity
                WHERE mission_id = :mission_id AND user_id = :user_id
                """,
                    dict(mission_id=mission_id, user_id=user_id),
                )
            ]

            def _get_root_activity_of_revision(activity):
                _act = activity
                if _act.type not in ["break", "rest"]:
                    while _act not in activities_to_keep:
                        _act = [a for a in acts if a.id == _act.revisee_id][0]
                    return _act
                else:
                    return None

            def _revise(activity):
                if activity.type not in ["break", "rest"]:
                    _act = _get_root_activity_of_revision(activity)
                else:
                    _act = [a for a in acts if a.id == activity.revisee_id][0]

                if activity.start_time == _act.start_time:
                    return

                previous_activity = previous_activity_at(_act.start_time)
                next_activity = next_activity_at(_act.start_time)
                small_shift = (
                    not previous_activity
                    or previous_activity.start_time < activity.start_time
                ) and (
                    not next_activity
                    or next_activity.start_time > activity.start_time
                )

                if not small_shift:
                    raise RuntimeError

                if previous_activity and (
                    previous_activity.end_time == _act.start_time
                    or previous_activity.end_time > activity.start_time
                ):
                    _soft_revise(
                        previous_activity,
                        activity.submitter_id,
                        activity.reception_time,
                        end_time=activity.start_time,
                    )

                if activity.type not in ["break", "rest"]:
                    _soft_revise(
                        _act,
                        activity.submitter_id,
                        activity.reception_time,
                        start_time=activity.start_time,
                    )

            def _soft_revise(
                activity,
                submitter_id,
                reception_time,
                start_time=None,
                end_time=None,
                remove_end_time=False,
            ):
                activities_to_keep[activity][reception_time] = RevisionData(
                    submitter_id=submitter_id,
                    start_time=start_time or activity.start_time,
                    end_time=None
                    if remove_end_time
                    else (end_time or activity.end_time),
                    context=None,
                    reception_time=reception_time,
                )
                activity.start_time = start_time or activity.start_time
                activity.end_time = (
                    None
                    if remove_end_time
                    else (end_time or activity.end_time)
                )

            def _log(activity):
                overlapping_act = activity_at(activity.start_time)
                overlapping_act_end_time = (
                    overlapping_act.end_time if overlapping_act else None
                )

                if overlapping_act:
                    _soft_revise(
                        overlapping_act,
                        activity.submitter_id,
                        activity.reception_time,
                        end_time=activity.start_time,
                    )
                if activity.type not in ["break", "rest"]:
                    next_activity = next_activity_at(activity.start_time)
                    if next_activity and overlapping_act_end_time:
                        activity.end_time = min(
                            overlapping_act_end_time, next_activity.start_time
                        )
                    elif next_activity:
                        activity.end_time = next_activity.start_time
                    elif overlapping_act:
                        activity.end_time = overlapping_act_end_time

                    activities_to_keep[activity][
                        activity.reception_time
                    ] = RevisionData(
                        submitter_id=activity.submitter_id,
                        start_time=activity.start_time,
                        end_time=activity.end_time,
                        context=activity.context,
                        reception_time=activity.reception_time,
                    )
                    current_valid_activities.add(activity)

            def _cancel(activity):
                previous_activity = previous_activity_at(activity.start_time)
                if (
                    previous_activity
                    and previous_activity.end_time == activity.start_time
                ):
                    previous_activity_end_time = activity.end_time
                    next_activity = next_activity_at(activity.start_time)
                    if (
                        next_activity
                        and next_activity.type == previous_activity.type
                        and (
                            activity.type == "break"
                            or next_activity.start_time == activity.end_time
                        )
                    ):
                        current_valid_activities.remove(next_activity)
                        next_activity.dismissed_at = activity.dismissed_at
                        next_activity.dismiss_author_id = (
                            activity.dismiss_author_id
                        )
                        next_activity.dismiss_context = (
                            activity.dismiss_context
                        )
                        previous_activity_end_time = next_activity.end_time
                    elif next_activity and activity.type == "break":
                        previous_activity_end_time = next_activity.start_time

                    _soft_revise(
                        previous_activity,
                        activity.dismiss_author_id,
                        activity.dismissed_at,
                        remove_end_time=True
                        if not previous_activity_end_time
                        else False,
                        end_time=previous_activity_end_time,
                    )

                root_activity = _get_root_activity_of_revision(activity)
                if root_activity:
                    current_valid_activities.remove(root_activity)
                    if root_activity != activity:
                        root_activity.dismissed_at = activity.dismissed_at
                        root_activity.dismiss_author_id = (
                            activity.dismiss_author_id
                        )
                        root_activity.dismiss_context = (
                            activity.dismiss_context
                        )

            def activity_at(time):
                overlapping_activities = [
                    a
                    for a in current_valid_activities
                    if a.start_time < time
                    and (not a.end_time or a.end_time > time)
                ]
                return (
                    overlapping_activities[0]
                    if overlapping_activities
                    else None
                )

            def next_activity_at(time):
                next_activities = sorted(
                    [
                        a
                        for a in current_valid_activities
                        if a.start_time > time
                    ],
                    key=lambda a: a.start_time,
                )
                return next_activities[0] if next_activities else None

            def previous_activity_at(time):
                next_activities = sorted(
                    [
                        a
                        for a in current_valid_activities
                        if a.start_time < time
                        and a.end_time
                        and a.end_time <= time
                    ],
                    key=lambda a: a.start_time,
                )
                return next_activities[-1] if next_activities else None

            for (
                reception_time,
                events,
            ) in activity_events_by_reception_time.items():
                if len(events) == 1 and events[0].type == "log":
                    _log(events[0].activity)

                elif len(events) == 1 and events[0].type == "revision":
                    _revise(events[0].activity)

                elif len(events) == 1 and events[0].type == "user_cancel":
                    a = events[0].activity
                    _cancel(a)

                elif len(events) == 2 and set([e.type for e in events]) == {
                    "log"
                }:
                    sorted_acts = sorted(
                        [e.activity for e in events],
                        key=lambda a: a.start_time,
                    )
                    for act in sorted_acts:
                        _log(act)

                elif len(events) == 2 and set([e.type for e in events]) == {
                    "log",
                    "no_activity_switch",
                }:
                    _acts = [e.activity for e in events]
                    if _acts[0].id != _acts[1].id:
                        a = [e.activity for e in events if e.type == "log"][0]
                        revised_activity = [
                            e.activity
                            for e in events
                            if e.type == "no_activity_switch"
                        ][0]
                        a.revisee_id = revised_activity.id
                        if a.start_time >= revised_activity.start_time:
                            raise RuntimeError
                        _revise(a)

                elif len(events) == 2 and set([e.type for e in events]) == {
                    "log",
                    "revision",
                }:
                    rev = [e for e in events if e.type == "revision"][0]
                    log = [e for e in events if e.type == "log"][0]
                    _revise(rev.activity)
                    _log(log.activity)

                elif len(
                    events
                ) == 2 and "break_or_rest_as_starting_activity" in set(
                    [e.type for e in events]
                ):
                    pass

                elif len(events) == 3 and set([e.type for e in events]) == {
                    "log",
                    "revision",
                    "no_activity_switch",
                }:
                    rev = [e for e in events if e.type == "revision"][0]
                    log = [e for e in events if e.type == "log"][0]
                    no_act_switch = [
                        e for e in events if e.type == "no_activity_switch"
                    ][0]
                    if log.activity.id == no_act_switch.activity.id:
                        _revise(rev.activity)
                    elif rev.activity.id == no_act_switch.activity.id:
                        assert (
                            log.activity.start_time < rev.activity.start_time
                        )
                        log.activity.revisee_id = no_act_switch.activity.id
                        _revise(log.activity)
                    else:
                        if (
                            log.activity.type == "break"
                            and log.activity.start_time
                            == rev.activity.start_time
                            and rev.activity.revisee_id == log.activity.id
                        ):
                            _log(log.activity)
                        else:
                            if not (
                                rev.activity.start_time
                                < log.activity.start_time
                                < no_act_switch.activity.start_time
                            ):
                                raise RuntimeError
                            _revise(rev.activity)
                            log.activity.revisee_id = no_act_switch.activity.id
                            _revise(log.activity)

                elif len(events) == 2 and set([e.type for e in events]) == {
                    "revision"
                }:
                    sorted_acts = sorted(
                        [e.activity for e in events],
                        key=lambda a: a.start_time,
                    )
                    for act in sorted_acts:
                        _revise(act)

                elif len(events) == 2 and set([e.type for e in events]) == {
                    "user_cancel",
                    "no_activity_switch",
                }:
                    cancel = [e for e in events if e.type == "user_cancel"][0]
                    _cancel(cancel.activity)

                elif len(events) == 4 and set([e.type for e in events]) == {
                    "log",
                    "no_activity_switch",
                }:
                    pass

                elif len(events) == 3 and set([e.type for e in events]) == {
                    "revision",
                    "user_cancel",
                    "no_activity_switch",
                }:
                    cancel = [e for e in events if e.type == "user_cancel"][0]
                    _cancel(cancel.activity)

                else:
                    raise RuntimeError

            activity_ids_to_remove = set(
                all_mission_activities_for_user
            ) - set([a.id for a in activities_to_keep])
            for a, revisions in activities_to_keep.items():
                sorted_revisions = [
                    r[1] for r in sorted(revisions.items(), key=lambda s: s[0])
                ]
                last_update_time = sorted_revisions[-1].reception_time
                session.execute(
                    """
                    UPDATE activity
                    SET
                        start_time = :start_time,
                        end_time = :end_time,
                        last_update_time = :last_update_time,
                        dismissed_at = :dismissed_at,
                        dismiss_author_id = :dismiss_author_id,
                        dismiss_type = null,
                        dismiss_received_at = null,
                        revised_by_id = null
                    WHERE id = :id
                    """,
                    dict(
                        id=a.id,
                        start_time=a.start_time,
                        end_time=a.end_time,
                        last_update_time=last_update_time,
                        dismissed_at=a.dismissed_at
                        if a not in current_valid_activities
                        else None,
                        dismiss_author_id=a.dismiss_author_id
                        if a not in current_valid_activities
                        else None,
                    ),
                )

                for index, r in enumerate(sorted_revisions):
                    session.execute(
                        """
                        INSERT INTO activity_version(
                            creation_time,
                            reception_time,
                            activity_id,
                            version,
                            start_time,
                            end_time,
                            context,
                            submitter_id
                        )
                        VALUES (
                            NOW(),
                            :reception_time,
                            :activity_id,
                            :version,
                            :start_time,
                            :end_time,
                            cast(:context as JSONB),
                            :submitter_id
                        )
                        """,
                        dict(
                            reception_time=r.reception_time,
                            activity_id=a.id,
                            version=index + 1,
                            start_time=r.start_time,
                            end_time=r.end_time,
                            context=json.dumps(r.context)
                            if r.context
                            else None,
                            submitter_id=r.submitter_id,
                        ),
                    )

            if activity_ids_to_remove:
                session.execute(
                    """
                    DELETE FROM activity
                    WHERE id in :activity_ids
                    """,
                    dict(activity_ids=tuple(activity_ids_to_remove)),
                )
    session.commit()


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "mission_end",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("reception_time", sa.DateTime(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["mission.id"],),
        sa.ForeignKeyConstraint(["submitter_id"], ["user.id"],),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "mission_id", "user_id", name="user_can_only_end_mission_once"
        ),
    )
    op.create_index(
        op.f("ix_mission_end_mission_id"),
        "mission_end",
        ["mission_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mission_end_submitter_id"),
        "mission_end",
        ["submitter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mission_end_user_id"),
        "mission_end",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "activity_version",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("reception_time", sa.DateTime(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "context",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activity.id"],),
        sa.ForeignKeyConstraint(["submitter_id"], ["user.id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version",
            "activity_id",
            name="unique_version_among_same_activity_versions",
        ),
    )
    op.create_index(
        op.f("ix_activity_version_activity_id"),
        "activity_version",
        ["activity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_version_submitter_id"),
        "activity_version",
        ["submitter_id"],
        unique=False,
    )
    op.add_column(
        "activity", sa.Column("end_time", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "activity", sa.Column("last_update_time", sa.DateTime(), nullable=True)
    )

    # Migrate activities
    op.drop_constraint("no_simultaneous_acknowledged_activities", "activity")
    op.drop_constraint("non_nullable_dismiss_type", "activity")
    _migrate_activities()

    op.drop_index("ix_activity_revised_by_id", table_name="activity")
    op.drop_constraint(
        "activity_revised_by_id_fkey", "activity", type_="foreignkey"
    )
    op.drop_column("activity", "revision_context")
    op.drop_column("activity", "context")
    op.drop_column("activity", "revised_by_id")
    op.drop_column("activity", "dismiss_type")
    op.drop_column("activity", "dismiss_received_at")

    op.alter_column("activity", "last_update_time", nullable=False)
    op.drop_constraint("activitytypes", "activity")
    op.alter_column(
        "activity",
        "type",
        type_=sa.Enum(
            "drive",
            "support",
            "work",
            name="activitytypes",
            native_enum=False,
        ),
        nullable=False,
    )

    op.create_check_constraint(
        "non_nullable_dismiss_info",
        "activity",
        "((dismissed_at is not null)::bool = (dismiss_author_id is not null)::bool)",
    )

    op.drop_column("employment", "dismiss_type")
    op.create_check_constraint(
        "non_nullable_dismiss_info",
        "employment",
        "((dismissed_at is not null)::bool = (dismiss_author_id is not null)::bool)",
    )

    op.drop_column("expenditure", "dismiss_type")
    op.create_check_constraint(
        "non_nullable_dismiss_info",
        "expenditure",
        "((dismissed_at is not null)::bool = (dismiss_author_id is not null)::bool)",
    )

    # Add new constraints
    op.create_check_constraint(
        "activity_version_start_time_before_reception_time",
        "activity_version",
        "(reception_time + interval '300 seconds' >= start_time)",
    )
    op.create_check_constraint(
        "activity_version_end_time_before_reception_time",
        "activity_version",
        "(end_time is null or (reception_time + interval '300 seconds' >= end_time))",
    )
    op.create_check_constraint(
        "activity_version_start_time_before_end_time",
        "activity_version",
        "(end_time is null or start_time < end_time)",
    )

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
    op.execute(
        """
        ALTER TABLE activity ADD CONSTRAINT no_sucessive_activities_with_same_type
        EXCLUDE USING GIST (
            user_id WITH =,
            type WITH =,
            tsrange(start_time, end_time, '[]') WITH &&
        )
        WHERE (dismissed_at is null)
        """
    )
    op.create_check_constraint(
        "activity_start_time_before_end_time",
        "activity",
        "(end_time is null or start_time < end_time)",
    )
    op.create_check_constraint(
        "activity_end_time_before_update_time",
        "activity",
        "(end_time is null or (last_update_time + interval '300 seconds' >= end_time))",
    )

    op.drop_constraint(
        "only_one_current_primary_employment_per_user", "employment"
    )
    op.execute(
        """
        ALTER TABLE employment ADD CONSTRAINT only_one_current_primary_employment_per_user
        EXCLUDE USING GIST (
            user_id WITH =,
            daterange(start_date, end_date, '[]') WITH &&
        )
        WHERE (is_primary AND validation_status != 'rejected' and dismissed_at is null)
        """
    )

    op.drop_constraint(
        "no_simultaneous_employments_for_the_same_company", "employment"
    )
    op.execute(
        """
        ALTER TABLE employment ADD CONSTRAINT no_simultaneous_employments_for_the_same_company
        EXCLUDE USING GIST (
            user_id WITH =,
            company_id WITH =,
            daterange(start_date, end_date, '[]') WITH &&
        )
        WHERE (validation_status != 'rejected' and dismissed_at is null)
        """
    )

    op.create_unique_constraint(None, "user", ["activation_email_token"])
    # ### end Alembic commands ###


def downgrade():
    pass
