from sqlalchemy.orm import selectinload, subqueryload, joinedload
from sqlalchemy import and_, or_, desc, Integer, Interval, literal_column
from datetime import datetime, date
from psycopg2.extras import DateTimeRange
from sqlalchemy.sql import func, case, extract, distinct
from functools import reduce
from dateutil.tz import gettz

from app import db
from app.helpers.pagination import parse_datetime_plus_id_cursor, to_connection
from app.helpers.time import to_datetime
from app.models import (
    User,
    Activity,
    Mission,
    Company,
    Employment,
    Expenditure,
    MissionValidation,
)
from app.models.activity import ActivityType
from app.models.expenditure import ExpenditureType
from app.models.location_entry import LocationEntry


def user_query_with_all_relations():
    return User.query.options(
        selectinload(User.activities)
        .options(selectinload(Activity.revisions))
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
        .options(selectinload(Activity.revisions))
    ).options(selectinload(Company.vehicles))


def _apply_time_range_filters(query, start_time, end_time):
    if type(start_time) is date:
        start_time = datetime(
            start_time.year, start_time.month, start_time.day
        )
    if type(end_time) is date:
        end_time = datetime(
            end_time.year, end_time.month, end_time.day, 23, 59, 59
        )
    if start_time or end_time:
        return query.filter(
            func.tsrange(Activity.start_time, Activity.end_time, "[]").op(
                "&&"
            )(DateTimeRange(start_time, end_time, "[)"))
        )

    return query


def query_activities(
    include_dismissed_activities=False,
    start_time=None,
    end_time=None,
    user_id=None,
):
    base_query = Activity.query

    if user_id:
        base_query = base_query.filter(Activity.user_id == user_id)

    if not include_dismissed_activities:
        base_query = base_query.filter(~Activity.is_dismissed)

    return _apply_time_range_filters(base_query, start_time, end_time)


def add_mission_relations(
    query, include_revisions=False, use_subqueries=False
):
    relationship_loading_technique = (
        subqueryload if use_subqueries else selectinload
    )
    mission_activities_subq = relationship_loading_technique(
        Mission.activities
    )
    if include_revisions:
        mission_activities_subq = mission_activities_subq.joinedload(
            Activity.revisions, innerjoin=True
        )

    return query.options(
        relationship_loading_technique(Mission.validations),
        relationship_loading_technique(Mission.expenditures),
        relationship_loading_technique(Mission.comments),
        relationship_loading_technique(Mission.vehicle),
        mission_activities_subq,
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
    only_non_validated_missions=False,
):
    from app.data_access.mission import MissionConnection

    company_mission_subq = Mission.query.with_entities(Mission.id).filter(
        Mission.company_id.in_(company_ids)
    )
    if only_non_validated_missions:
        company_mission_subq = (
            company_mission_subq.join(Mission.validations, isouter=True)
            .group_by(Mission.id)
            .having(
                func.bool_and(
                    or_(
                        and_(
                            MissionValidation.is_admin.is_(None),
                            MissionValidation.user_id.isnot(None),
                        ),
                        and_(
                            ~MissionValidation.is_admin,
                            MissionValidation.user_id.isnot(None),
                        ),
                    )
                )
            )
        )

    company_mission_subq = company_mission_subq.subquery()

    if after:
        max_time, id_ = parse_datetime_plus_id_cursor(after)
        end_time = min(max_time, end_time) if end_time else max_time

    mission_id_query = (
        query_activities(start_time=start_time, end_time=end_time)
        .join(company_mission_subq, Activity.mission)
        .group_by(Activity.mission_id)
        .with_entities(
            Activity.mission_id.label("mission_id"),
            func.min(Activity.start_time).label("mission_start_time"),
        )
        .from_self()
        .with_entities("mission_id", "mission_start_time")
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
    tz = gettz(tzname)
    if after:
        max_time, user_id_ = parse_datetime_plus_id_cursor(after)
        max_date = max_time.date()
        end_date = min(max_date, end_date) if end_date else max_date

    query = (
        Activity.query.join(Mission)
        .join(
            Expenditure,
            and_(
                Activity.user_id == Expenditure.user_id,
                Activity.mission_id == Expenditure.mission_id,
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
            func.generate_series(
                func.date_trunc(
                    "day",
                    func.timezone(
                        tzname, func.timezone("UTC", Activity.start_time),
                    ),
                ),
                func.timezone(
                    tzname,
                    func.coalesce(
                        func.timezone("UTC", Activity.end_time), func.now(),
                    ),
                ),
                "1 day",
            ).label("day"),
        )
        .filter(
            Mission.company_id == company_id,
            ~Activity.is_dismissed,
            or_(
                Activity.end_time.is_(None),
                Activity.start_time != Activity.end_time,
            ),
        )
    )

    query = _apply_time_range_filters(
        query,
        to_datetime(start_date, tz_for_date=tz),
        to_datetime(
            end_date, tz_for_date=tz, convert_dates_to_end_of_day_times=True
        ),
    )

    has_next_page = False
    if first:
        activity_first = max(first * 5, 200)
        query = query.order_by(desc("day"), desc(Activity.user_id)).limit(
            activity_first + 1
        )
        has_next_page = query.count() > activity_first

    query = query.subquery()

    query = (
        db.session.query(query)
        .group_by(
            query.c.user_id, query.c.day, query.c.mission_id, query.c.name
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
                        [(query.c.expenditure_type == e_type.value, 1)],
                        else_=0,
                    )
                ).label(f"n_{e_type.value}_expenditures")
                for e_type in ExpenditureType
            ],
        )
        .subquery()
    )

    query = (
        db.session.query(query)
        .group_by(query.c.user_id, query.c.day)
        .with_entities(
            query.c.user_id.label("user_id"),
            query.c.day,
            func.array_agg(distinct(query.c.mission_name)).label(
                "mission_names"
            ),
            func.min(query.c.start_time).label("start_time"),
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
