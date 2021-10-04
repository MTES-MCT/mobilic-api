from app import db
from app.domain.permissions import check_actor_can_log_on_mission_for_user_at
from app.helpers.errors import ExpenditureDateNotIncludedInMissionRangeError
from app.models.expenditure import Expenditure
from app.helpers.authorization import AuthorizationError


def check_date_is_during_mission(spending_date, mission, user):
    mission_activities = mission.activities_for(user)

    if len(mission_activities) == 0:
        raise ExpenditureDateNotIncludedInMissionRangeError()

    mission_start = mission_activities[0].start_time.date()
    mission_end = mission_activities[-1].end_time.date()

    if spending_date < mission_start or spending_date > mission_end:
        raise ExpenditureDateNotIncludedInMissionRangeError()


def log_expenditure(
    submitter, user, mission, type, reception_time, spending_date
):
    # 1. Check permissions
    check_actor_can_log_on_mission_for_user_at(
        submitter, user, mission, reception_time
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
    )
    db.session.add(expenditure)
    return expenditure
