from sqlalchemy.orm import selectinload, subqueryload, joinedload
from sqlalchemy import (
    and_,
    or_,
    desc,
    Integer,
    Interval,
    literal_column,
    column,
    TEXT,
)
from sqlalchemy.dialects.postgresql import array
from datetime import timezone
from psycopg2.extras import DateTimeRange
from sqlalchemy.sql import func, case, extract, distinct
from functools import reduce
from dateutil.tz import gettz

from app import db
from app.helpers.pagination import parse_datetime_plus_id_cursor, to_connection
from app.helpers.time import to_datetime, to_tz
from app.models import (
    User,
    Activity,
    Mission,
    Company,
    Employment,
    Expenditure,
    MissionValidation,
    MissionEnd,
)
from app.models.activity import ActivityType
from app.models.controller_control import ControllerControl
from app.models.expenditure import ExpenditureType
from app.models.location_entry import LocationEntry


# https://docs.sqlalchemy.org/en/14/orm/loading_relationships.html#what-kind-of-loading-to-use


def user_query_with_all_relations():
    return User.query.options(
        selectinload(User.activities)
        .options(selectinload(Activity.versions))
        .options(
            selectinload(Activity.mission)
            .options(selectinload(Mission.validations))
            .options(selectinload(Mission.expenditures))
            .options(selectinload(Mission.activities))
        )
    ).options(
        selectinload(User.employments)
        .selectinload(Employment.company)
        .options(
            selectinload(Company.employments).selectinload(Employment.user)
        )
        .options(selectinload(Company.vehicles))
    )


def company_queries_with_all_relations():
    return Company.query.options(
        selectinload(Company.employments)
        .selectinload(Employment.user)
        .selectinload(User.activities)
        .options(
            selectinload(Activity.mission).selectinload(Mission.expenditures)
        )
        .options(selectinload(Activity.versions))
    ).options(selectinload(Company.vehicles))


def _apply_time_range_filters_to_activity_query(query, start_time, end_time):
    start_time = to_datetime(start_time)
    end_time = to_datetime(end_time, date_as_end_of_day=True)
    if start_time or end_time:
        return query.filter(
            func.tsrange(
                Activity.start_time,
                case(
                    [
                        (
                            Activity.is_dismissed,
                            func.coalesce(
                                Activity.end_time,
                                func.greatest(
                                    Activity.start_time, Activity.dismissed_at
                                ),
                            ),
                        )
                    ],
                    else_=Activity.end_time,
                ),
                "[]",
            ).op("&&")(
                DateTimeRange(
                    to_tz(start_time, timezone.utc) if start_time else None,
                    to_tz(end_time, timezone.utc) if end_time else None,
                    "[]",
                )
            )
        )

    return query


def query_activities(
    include_dismissed_activities=False,
    start_time=None,
    end_time=None,
    user_id=None,
    company_ids=None,
    max_reception_time=None,
    mission_id=None,
):
    base_query = Activity.query

    if user_id:
        base_query = base_query.filter(Activity.user_id == user_id)

    if max_reception_time:
        base_query = base_query.filter(
            Activity.reception_time <= max_reception_time
        )

    if mission_id:
        base_query = base_query.filter(Activity.mission_id == mission_id)

    if not include_dismissed_activities:
        base_query = base_query.filter(~Activity.is_dismissed)

    if company_ids is not None:
        base_query = base_query.join(Activity.mission).filter(
            Mission.company_id.in_(company_ids)
        )

    return _apply_time_range_filters_to_activity_query(
        base_query, start_time, end_time
    )


def add_mission_relations(
    query, include_revisions=False, use_subqueries=False
):
    relationship_loading_technique = (
        subqueryload if use_subqueries else selectinload
    )
    mission_activities_subq = (
        relationship_loading_technique
        if not include_revisions
        else selectinload
    )(Mission.activities)
    if include_revisions:
        mission_activities_subq = mission_activities_subq.joinedload(
            Activity.versions, innerjoin=True
        )

    return query.options(
        mission_activities_subq,
        relationship_loading_technique(Mission.validations),
        # To be commented locally on init regulation alerts only!
        # (all the relationships below)
        relationship_loading_technique(Mission.expenditures),
        relationship_loading_technique(Mission.comments),
        relationship_loading_technique(Mission.vehicle),
        relationship_loading_technique(Mission.location_entries).options(
            joinedload(LocationEntry._address),
            joinedload(LocationEntry._company_known_address),
        ),
    )


def query_company_missions(
    company_ids,
    start_time=None,
    end_time=None,
    first=None,
    after=None,
    only_ended_missions=False,
):
    from app.data_access.mission import MissionConnection

    # This first query yields the ids of the missions that fall in the company scope
    company_mission_subq = Mission.query.with_entities(Mission.id).filter(
        Mission.company_id.in_(company_ids)
    )

    if only_ended_missions:
        company_mission_subq = (
            company_mission_subq.join(
                Activity, Activity.mission_id == Mission.id
            )
            .join(
                MissionEnd,
                and_(
                    Activity.mission_id == MissionEnd.mission_id,
                    Activity.user_id == MissionEnd.user_id,
                ),
                isouter=True,
            )
            .filter(~Activity.is_dismissed)
            .group_by(Mission.id)
            .having(func.every(MissionEnd.id.isnot(None)))
        )

    company_mission_subq = company_mission_subq.subquery()

    # Cursor pagination : missions are sorted by descending start time (start time of the earliest activity) and id
    if after:
        max_time, id_ = parse_datetime_plus_id_cursor(after)
        end_time = min(max_time, end_time) if end_time else max_time

    # This query yields the ids of the missions that are in the requested period scope, on top of being in the requested company scope
    mission_id_query = (
        query_activities(start_time=start_time, end_time=end_time)
        .join(company_mission_subq, Activity.mission)
        .group_by(Activity.mission_id)
        .with_entities(
            Activity.mission_id.label("mission_id"),
            func.min(Activity.start_time).label("mission_start_time"),
        )
        .from_self()
        .with_entities(column("mission_id"), column("mission_start_time"))
    )

    if after:
        mission_id_query = mission_id_query.filter(
            or_(
                literal_column("mission_start_time") < max_time,
                and_(
                    literal_column("mission_start_time") == max_time,
                    literal_column("mission_id") < id_,
                ),
            )
        )

    # Hard cap on the number of records returned is 1000
    actual_first = min(first or 1000, 1000)
    mission_id_query = mission_id_query.order_by(
        desc("mission_start_time"), desc("mission_id")
    ).limit(actual_first + 1)

    missions_ids_and_start_times = [
        (getattr(m, "mission_id"), getattr(m, "mission_start_time"))
        for m in mission_id_query.all()
    ]

    mission_id_to_cursor = {
        m[0]: f"{str(m[1])},{m[0]}" for m in missions_ids_and_start_times
    }

    # The second query that yields the missions themselves, from the ids we retrieved earlier
    mission_query = add_mission_relations(
        Mission.query, use_subqueries=len(missions_ids_and_start_times) > 500
    )
    missions = mission_query.filter(
        Mission.id.in_([m[0] for m in missions_ids_and_start_times])
    ).all()
    missions = {mission.id: mission for mission in missions}

    return to_connection(
        [missions[m[0]] for m in missions_ids_and_start_times],
        connection_cls=MissionConnection,
        has_next_page=False,
        get_cursor=lambda m: mission_id_to_cursor.get(m.id, None),
        first=actual_first,
    )


def query_work_day_stats(
    company_id,
    start_date=None,
    end_date=None,
    first=None,
    after=None,
    tzname="Europe/Paris",
):
    # The following is a bit complex because we want to compute day-centric statistics from data that are not day-centric (an activity period can for instance span over several days)

    tz = gettz(tzname)

    # Cursor pagination : work days are sorted by descending date and user id
    if after:
        max_time, user_id_ = parse_datetime_plus_id_cursor(after)
        max_date = max_time.date()
        end_date = min(max_date, end_date) if end_date else max_date

    # First query returns all the activities that will be used to compute statistics, split by days
    query = (
        Activity.query.join(Mission)
        .join(
            Expenditure,
            and_(
                Activity.user_id == Expenditure.user_id,
                Activity.mission_id == Expenditure.mission_id,
                ~Expenditure.is_dismissed,
            ),
            isouter=True,
        )
        .with_entities(
            Activity.id,
            Activity.user_id,
            Activity.mission_id,
            Mission.name,
            Activity.start_time,
            Activity.end_time,
            Activity.type,
            Expenditure.id.label("expenditure_id"),
            Expenditure.type.label("expenditure_type"),
            Expenditure.spending_date.label("expenditure_spending_date"),
            # Split an activity by the number of days it overlaps.
            func.generate_series(
                func.date_trunc(
                    "day",
                    func.timezone(
                        tzname,
                        func.timezone("UTC", Activity.start_time),
                    ),
                ),
                func.timezone(
                    tzname,
                    func.coalesce(
                        func.timezone("UTC", Activity.end_time),
                        func.now(),
                    ),
                ),
                "1 day",
            ).label("day"),
        )
        .filter(
            Mission.company_id == company_id,
            # Keep only activities that are not dismissed and have a non-zero period
            ~Activity.is_dismissed,
        )
    )

    query = _apply_time_range_filters_to_activity_query(
        query,
        to_datetime(start_date, tz_for_date=tz),
        to_datetime(end_date, tz_for_date=tz, date_as_end_of_day=True),
    )

    has_next_page = False
    if first:
        # Retrieve at least 200 activities to ensure that we have at least a full work day
        activity_first = max(first * 5, 200)
        query = query.order_by(desc("day"), desc(Activity.user_id)).limit(
            activity_first + 1
        )
        has_next_page = query.count() > activity_first

    query = query.subquery()

    # Now compute the statistics from the activities in the requested scope
    ## First round groups by user id, day and mission
    query = (
        db.session.query(query)
        .group_by(
            query.c.user_id,
            query.c.day,
            query.c.mission_id,
            query.c.name,
        )
        .with_entities(
            query.c.user_id.label("user_id"),
            query.c.day,
            func.timezone("UTC", func.timezone(tzname, query.c.day)).label(
                "utc_day_start"
            ),
            query.c.mission_id.label("mission_id"),
            query.c.name.label("mission_name"),
            func.min(
                func.greatest(
                    query.c.start_time,
                    func.timezone("UTC", func.timezone(tzname, query.c.day)),
                )
            ).label("start_time"),
            func.max(query.c.start_time).label("last_activity_start_time"),
            func.max(
                func.least(
                    func.timezone(
                        "UTC",
                        func.timezone(
                            tzname, query.c.day + func.cast("1 day", Interval)
                        ),
                    ),
                    func.coalesce(query.c.end_time, func.now()),
                )
            ).label("end_time"),
            func.bool_or(
                and_(
                    query.c.end_time.is_(None),
                    query.c.day == func.current_date(),
                )
            ).label("is_running"),
            *[
                func.sum(
                    case(
                        [
                            (
                                query.c.type == a_type.value,
                                extract(
                                    "epoch",
                                    func.least(
                                        func.timezone(
                                            "UTC",
                                            func.timezone(
                                                tzname,
                                                query.c.day
                                                + func.cast("1 day", Interval),
                                            ),
                                        ),
                                        func.coalesce(
                                            query.c.end_time, func.now()
                                        ),
                                    )
                                    - func.greatest(
                                        query.c.start_time,
                                        func.timezone(
                                            "UTC",
                                            func.timezone(tzname, query.c.day),
                                        ),
                                    ),
                                ),
                            )
                        ],
                        else_=0,
                    )
                ).label(f"{a_type.value}_duration")
                for a_type in ActivityType
            ],
            func.greatest(
                func.count(distinct(query.c.expenditure_id)), 1
            ).label("n_exp_dups"),
            func.count(distinct(query.c.id)).label("n_act_dups"),
            *[
                func.sum(
                    case(
                        [
                            (
                                and_(
                                    query.c.expenditure_type == e_type.value,
                                    query.c.expenditure_spending_date
                                    == query.c.day,
                                ),
                                1,
                            )
                        ],
                        else_=0,
                    )
                ).label(f"n_{e_type.value}_expenditures")
                for e_type in ExpenditureType
            ],
        )
        .subquery()
    )

    ## Second round further groups by user id and day : that is the scale we want
    query = (
        db.session.query(query)
        .group_by(query.c.user_id, query.c.day)
        .with_entities(
            query.c.user_id.label("user_id"),
            query.c.day,
            func.array_agg(
                distinct(
                    array(
                        [
                            func.cast(query.c.mission_id, TEXT),
                            query.c.mission_name,
                        ]
                    )
                )
            ).label("mission_names"),
            func.min(query.c.start_time).label("start_time"),
            func.max(query.c.last_activity_start_time).label(
                "last_activity_start_time"
            ),
            func.max(query.c.end_time).label("end_time"),
            func.bool_or(query.c.is_running).label("is_running"),
            *[
                func.sum(
                    getattr(query.c, f"{a_type.value}_duration")
                    / query.c.n_exp_dups
                )
                .cast(Integer)
                .label(f"{a_type.value}_duration")
                for a_type in ActivityType
            ],
            *[
                func.sum(
                    getattr(query.c, f"n_{e_type.value}_expenditures")
                    / query.c.n_act_dups
                )
                .cast(Integer)
                .label(f"n_{e_type.value}_expenditures")
                for e_type in ExpenditureType
            ],
        )
        .order_by(desc("day"), desc("user_id"))
        .subquery()
    )

    query = db.session.query(query).with_entities(
        *query.c,
        extract("epoch", query.c.end_time - query.c.start_time).label(
            "service_duration"
        ),
        reduce(
            lambda a, b: a + b,
            [
                getattr(query.c, f"{a_type.value}_duration")
                for a_type in ActivityType
                if a_type != ActivityType.TRANSFER
            ],
        ).label("total_work_duration"),
    )

    results = query.all()
    if after:
        results = [
            r
            for r in results
            if r.day.date() < max_date
            or (r.day.date() == max_date and r.user_id < user_id_)
        ]

    if first:
        if has_next_page:
            # The last work day may be incomplete because we didn't fetch all the activities => remove it
            results = results[:-1]
        if len(results) > first:
            results = results[:first]
            has_next_page = True

    return results, has_next_page


def query_controls(
    controller_user_id,
    start_time=None,
    end_time=None,
    controls_type=None,
    limit=None,
):
    base_query = ControllerControl.query.filter(
        ControllerControl.controller_id == controller_user_id
    )

    if start_time:
        base_query = base_query.filter(
            ControllerControl.creation_time >= to_datetime(start_time)
        )

    if end_time:
        base_query = base_query.filter(
            ControllerControl.creation_time
            <= to_datetime(end_time, date_as_end_of_day=True)
        )

    if controls_type:
        base_query = base_query.filter(
            ControllerControl.control_type == controls_type
        )

    if limit:
        base_query = base_query.order_by(
            desc(ControllerControl.creation_time)
        ).limit(limit)

    return base_query
