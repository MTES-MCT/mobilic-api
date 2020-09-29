from app import db
from app.domain.permissions import can_user_log_on_mission_at
from app.helpers.errors import AuthorizationError, DuplicateExpendituresError
from app.models.expenditure import Expenditure


def log_expenditure(submitter, user, mission, type, reception_time):
    # 1. Check permissions
    if not can_user_log_on_mission_at(
        submitter, mission, reception_time
    ) or not can_user_log_on_mission_at(user, mission, reception_time):
        raise AuthorizationError(
            f"The user is not authorized to log for this mission"
        )

    # 2. Log the expenditure
    expenditure = Expenditure(
        type=type,
        reception_time=reception_time,
        mission=mission,
        user=user,
        submitter=submitter,
    )
    db.session.add(expenditure)
