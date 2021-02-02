from sqlalchemy.orm import selectinload, subqueryload, joinedload
from sqlalchemy import and_, or_, desc, Integer
from datetime import datetime, date
from psycopg2.extras import DateTimeRange
from sqlalchemy.sql import func, case, extract, distinct
from functools import reduce

from app import db
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
        mission_activities_subq,
        subqueryload(Mission.location_entries).options(
            joinedload(LocationEntry._address),
            joinedload(LocationEntry._company_known_address),
        ),
    )


def query_company_missions(
    company_id,
    start_time=None,
    end_time=None,
    limit=None,
    only_non_validated_missions=False,
):
    company_mission_subq = Mission.query.with_entities(Mission.id).filter(
        Mission.company_id == company_id
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

    mission_id_query = (
        query_activities(start_time=start_time, end_time=end_time)
        .join(company_mission_subq, Activity.mission)
        .group_by(Activity.mission_id)
        .with_entities(
            Activity.mission_id.label("mission_id"),
            func.min(Activity.start_time).label("mission_start_time"),
        )
        .from_self()
        .with_entities("mission_id")
        .order_by(desc("mission_start_time"))
        .limit(limit)
    )

    mission_query = add_mission_relations(Mission.query)

    if start_time or end_time or limit:
        mission_ids = mission_id_query.all()
        mission_query = mission_query.filter(Mission.id.in_(mission_ids))
    else:
        mission_query = mission_query.filter(Mission.company_id == company_id)

    missions = mission_query.all()
    return missions


def query_work_day_stats(
    company_id, start_time=None, end_time=None, limit=None
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
        .with_entities(Activity.id)
        .filter(Mission.company_id == company_id, ~Activity.is_dismissed)
    )

    query = _apply_time_range_filters(query, start_time, end_time)

    query = (
        query.group_by(Activity.user_id, Activity.mission_id)
        .with_entities(
            Activity.user_id.label("user_id"),
            Activity.mission_id.label("mission_id"),
            func.min(Activity.start_time).label("start_time"),
            func.max(func.coalesce(Activity.end_time, func.now())).label(
                "end_time"
            ),
            func.bool_or(Activity.end_time.is_(None)).label("is_running"),
            *[
                func.sum(
                    case(
                        [
                            (
                                Activity.type == a_type.value,
                                extract(
                                    "epoch",
                                    func.coalesce(
                                        Activity.end_time, func.now()
                                    )
                                    - Activity.start_time,
                                ),
                            )
                        ],
                        else_=0,
                    )
                ).label(f"{a_type.value}_duration")
                for a_type in ActivityType
            ],
            func.greatest(func.count(distinct(Expenditure.id)), 1).label(
                "n_exp_dups"
            ),
            func.count(distinct(Activity.id)).label("n_act_dups"),
            *[
                func.sum(
                    case([(Expenditure.type == e_type.value, 1)], else_=0)
                ).label(f"n_{e_type.value}_expenditures")
                for e_type in ExpenditureType
            ],
        )
        .subquery()
    )

    query = (
        db.session.query(query)
        .group_by(query.c.user_id, "day")
        .with_entities(
            query.c.user_id.label("user_id"),
            func.date_trunc("day", query.c.start_time).label("day"),
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
