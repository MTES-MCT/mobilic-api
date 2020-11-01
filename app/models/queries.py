from sqlalchemy.orm import selectinload
from datetime import datetime, date
from psycopg2.extras import DateTimeRange
from sqlalchemy.sql import func

from app.models import User, Activity, Mission, Company, Employment


def user_query_with_activities():
    return User.query.options(selectinload(User.activities))


def user_query_with_all_relations():
    return User.query.options(
        selectinload(User.activities)
        .selectinload(Activity.mission)
        .options(selectinload(Mission.validations))
        .options(selectinload(Mission.expenditures))
        .options(selectinload(Mission.activities))
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

    if type(start_time) is date:
        start_time = datetime(
            start_time.year, start_time.month, start_time.day
        )
    if type(end_time) is date:
        end_time = datetime(
            end_time.year, end_time.month, end_time.day, 23, 59, 59
        )
    if start_time or end_time:
        base_query = base_query.filter(
            func.tsrange(Activity.start_time, Activity.end_time, "[)").op(
                "&&"
            )(DateTimeRange(start_time, end_time, "[)"))
        )

    return base_query


def query_company_missions(
    company_id,
    start_time=None,
    end_time=None,
    limit=None,
    include_empty_missions=False,
):
    activities_in_period = (
        query_activities(start_time=start_time, end_time=end_time)
        .with_entities(Activity.mission_id)
        .distinct()
        .group_by(Activity.mission_id)
        .with_entities(
            Activity.mission_id,
            func.min(Activity.start_time).label("mission_start_time"),
        )
        .subquery()
    )

    mission_query = (
        Mission.query.options(selectinload(Mission.validations))
        .options(selectinload(Mission.expenditures))
        .options(
            selectinload(Mission.activities).selectinload(Activity.revisions)
        )
        .filter(Mission.company_id == company_id)
        .from_self()
    )

    if not include_empty_missions:
        return (
            mission_query.join(activities_in_period)
            .order_by(activities_in_period.c.mission_start_time.desc())
            .limit(limit)
        )

    if not start_time and not end_time and not limit:
        return mission_query

    return (
        mission_query.join(activities_in_period, isouter=True)
        .order_by(
            func.coalesce(
                activities_in_period.c.mission_start_time,
                Mission.reception_time,
            ).desc()
        )
        .limit(limit)
    )
