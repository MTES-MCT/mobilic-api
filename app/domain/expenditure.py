from app import db
from app.domain.permissions import can_user_log_on_mission_at
from app.helpers.errors import AuthorizationError, DuplicateExpenditureError
from app.models.expenditure import Expenditure


def log_expenditure(submitter, user, mission, type, reception_time):
    # 1. Check permissions
    if not can_user_log_on_mission_at(
        submitter, mission, reception_time
    ) or not can_user_log_on_mission_at(user, mission, reception_time):
        raise AuthorizationError(
            f"The user is not authorized to log for this mission"
        )

    # 2. Ensure that at maximum one expenditure can be logged per type, mission and user
    current_expenditures = mission.expenditures_for(user)

    current_expenditures_matching_type = [
        e for e in current_expenditures if e.type == type
    ]

    if current_expenditures_matching_type:
        raise DuplicateExpenditureError(
            f"A {type} expenditure is already logged for {mission} and {user}"
        )

    # 3. Log the expenditure
    expenditure = Expenditure(
        type=type,
        reception_time=reception_time,
        mission=mission,
        user=user,
        submitter=submitter,
    )
    db.session.add(expenditure)
