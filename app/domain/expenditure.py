from app import db
from app.domain.permissions import check_actor_can_log_on_mission_for_user_at
from app.models.expenditure import Expenditure


def log_expenditure(submitter, user, mission, type, reception_time):
    # 1. Check permissions
    check_actor_can_log_on_mission_for_user_at(
        submitter, user, mission, reception_time
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
    return expenditure
