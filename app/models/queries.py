from sqlalchemy.orm import selectinload

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


def mission_query_with_activities():
    return Mission.query.options(selectinload(Mission.validations)).options(
        selectinload(Mission.activities)
    )


def mission_query_with_expenditures():
    return Mission.query.options(selectinload(Mission.expenditures))


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
