from sqlalchemy.orm import selectinload
from datetime import datetime, date

from app.models import User, Activity, Mission, Company, Employment


def user_query_with_activities():
    return User.query.options(selectinload(User.activities))


def user_query_with_all_relations():
    return User.query.options(
        selectinload(User.activities)
        .selectinload(Activity.mission)
        .options(selectinload(Mission.validations))
        .options(selectinload(Mission.expenditures))
        .options(
            selectinload(Mission.activities).selectinload(Activity.revisee)
        )
    ).options(
        selectinload(User.employments)
        .selectinload(Employment.company)
        .options(
            selectinload(Company.employments).selectinload(Employment.user)
        )
        .options(selectinload(Company.vehicles))
    )


def mission_query_with_relations():
    return (
        Mission.query.options(selectinload(Mission.validations))
        .options(selectinload(Mission.activities))
        .options(selectinload(Mission.expenditures))
    )


def company_queries_with_all_relations():
    return Company.query.options(
        selectinload(Company.employments)
        .selectinload(Employment.user)
        .selectinload(User.activities)
        .options(
            selectinload(Activity.mission).selectinload(Mission.expenditures)
        )
        .options(selectinload(Activity.revisee))
    ).options(selectinload(Company.vehicles))


def query_activities(
    include_dismisses_and_revisions=False,
    start_time=None,
    end_time=None,
    user_id=None,
):
    base_query = Activity.query

    if user_id:
        base_query = base_query.filter(Activity.user_id == user_id)

    if not include_dismisses_and_revisions:
        base_query = base_query.filter(Activity.is_acknowledged)

    if type(start_time) is date:
        start_time = datetime(
            start_time.year, start_time.month, start_time.day
        )
    if type(end_time) is date:
        end_time = datetime(
            end_time.year, end_time.month, end_time.day, 23, 59, 59
        )
    if start_time:
        base_query = base_query.filter(Activity.start_time >= start_time)
    if end_time:
        base_query = base_query.filter(Activity.start_time <= end_time)

    return base_query


def query_company_missions(company_id, start_time=None, end_time=None):
    activities_in_period = query_activities(
        start_time=start_time, end_time=end_time
    ).subquery()

    return (
        Mission.query.options(selectinload(Mission.validations))
        .options(selectinload(Mission.expenditures))
        .options(
            selectinload(Mission.activities)
            .options(selectinload(Activity.user))
            .options(selectinload(Activity.revisee))
        )
        .filter(Mission.company_id == company_id)
        .join(activities_in_period)
    )
