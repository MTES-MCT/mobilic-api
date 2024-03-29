from app import db
from app.helpers.errors import ExpenditureDateNotIncludedInMissionRangeError
from app.domain.permissions import check_actor_can_write_on_mission
from app.models.expenditure import Expenditure
from app.helpers.authorization import AuthorizationError


def check_date_is_during_mission(spending_date, mission, user):
    mission_activities = mission.activities_for(user)

    if len(mission_activities) == 0:
        raise ExpenditureDateNotIncludedInMissionRangeError()

    mission_start = mission_activities[0].start_time.date()
    mission_end = (
        mission_activities[-1].end_time.date()
        if mission_activities[-1].end_time
        else None
    )

    if spending_date < mission_start or (
        mission_end and spending_date > mission_end
    ):
        raise ExpenditureDateNotIncludedInMissionRangeError()


def log_expenditure(
    submitter,
    user,
    mission,
    type,
    reception_time,
    spending_date,
    creation_time=None,
):
    # 1. Check permissions
    check_actor_can_write_on_mission(
        submitter, mission, user, at=spending_date
    )
    if not mission.company.require_expenditures:
        raise AuthorizationError(
            "Expenditures have been disabled for this company"
        )

    # 2. Consistency check
    check_date_is_during_mission(spending_date, mission, user)

    # 3. Log the expenditure
    expenditure = Expenditure(
        type=type,
        reception_time=reception_time,
        mission=mission,
        user=user,
        submitter=submitter,
        spending_date=spending_date,
        creation_time=creation_time,
    )
    db.session.add(expenditure)
    return expenditure
