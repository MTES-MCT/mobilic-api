from sqlalchemy.orm import selectinload, subqueryload, joinedload
from sqlalchemy import and_, or_, desc, Integer, Interval, text
from datetime import datetime, date
from psycopg2.extras import DateTimeRange
from sqlalchemy.sql import func, case, extract, distinct
from functools import reduce
from collections import OrderedDict
from base64 import b64decode, b64encode

from app import db
from app.helpers.errors import InvalidParamsError
from app.helpers.pagination import (
    paginate_query,
    parse_datetime_plus_id_cursor,
)
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


def add_mission_relations(query, include_revisions=False):
    mission_activities_subq = subqueryload(Mission.activities)
    if include_revisions:
        mission_activities_subq = mission_activities_subq.joinedload(
            Activity.revisions, innerjoin=True
        )

    return query.options(
        subqueryload(Mission.validations),
        subqueryload(Mission.expenditures),
        subqueryload(Mission.comments),
        subqueryload(Mission.vehicle),
        mission_activities_subq,
        subqueryload(Mission.location_entries).options(
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
        max_time, _ = parse_datetime_plus_id_cursor(after)
        end_time = min(max_time, end_time) if end_time else max_time

    mission_id_subquery = (
        query_activities(start_time=start_time, end_time=end_time)
        .join(company_mission_subq, Activity.mission)
        .group_by(Activity.mission_id)
        .with_entities(
            Activity.mission_id.label("mission_id"),
            func.min(Activity.start_time).label("mission_start_time"),
        )
        .from_self()
        .with_entities("mission_id", "mission_start_time")
        .subquery()
    )

    mission_id_query = db.session.query(mission_id_subquery)

    def cursor_to_filter(cs):
        max_start_time, id_ = cs.split(",")
        max_start_time = datetime.fromisoformat(max_start_time)
        id_ = int(id_)
        return or_(
            mission_id_subquery.c.mission_start_time < max_start_time,
            and_(
                mission_id_subquery.c.mission_start_time == max_start_time,
                mission_id_subquery.c.mission_id < id_,
            ),
        )

    mission_id_results, page_info = paginate_query(
        mission_id_query,
        item_to_cursor=lambda item: f"{str(getattr(item, 'mission_start_time'))},{getattr(item, 'mission_id')}",
        cursor_to_filter=cursor_to_filter,
        orders=(
            desc(mission_id_subquery.c.mission_start_time),
            desc(mission_id_subquery.c.mission_id),
        ),
        first=first,
        after=after,
        max_first=200,
    )

    mission_query = add_mission_relations(Mission.query)
    mission_ids_and_cursors = [
        (getattr(r["node"], "mission_id"), r["cursor"])
        for r in mission_id_results
    ]
    missions = mission_query.filter(
        Mission.id.in_([m[0] for m in mission_ids_and_cursors])
    ).all()
    missions = {mission.id: mission for mission in missions}

    return MissionConnection(
        edges=[
            MissionConnection.Edge(node=missions[id_], cursor=cursor)
            for id_, cursor in mission_ids_and_cursors
        ],
        page_info=page_info,
    )


def query_work_day_stats(
    company_id,
    start_time=None,
    end_time=None,
    limit=None,
    tzname="Europe/Paris",
):
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
            Activity.start_time != Activity.end_time,
        )
    )

    query = _apply_time_range_filters(query, start_time, end_time).subquery()

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
        .order_by(desc("day"))
        .limit(limit)
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

    return query.all()
