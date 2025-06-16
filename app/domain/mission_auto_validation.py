from flask_jwt_extended import current_user

from app import db
from app.models import MissionAutoValidation


def create_mission_auto_validation(for_user, mission, reception_time):

    from app import company_admin

    is_user_admin = company_admin(current_user, mission.company_id)

    auto_validation = MissionAutoValidation(
        mission=mission,
        is_admin=is_user_admin,
        user=for_user,
        reception_time=reception_time,
    )
    db.session.add(auto_validation)
