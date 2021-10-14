from datetime import datetime

from app import db, app
from app.domain.permissions import company_admin
from app.helpers.errors import (
    NoActivitiesToValidateError,
    MissionStillRunningError,
)
from app.models import MissionValidation, MissionEnd
from app.helpers.authorization import AuthorizationError


def validate_mission(mission, submitter, for_user=None):
    validation_time = datetime.now()
    is_admin_validation = company_admin(submitter, mission.company_id)

    user = for_user or (submitter if not is_admin_validation else None)

    if not is_admin_validation and user.id != submitter.id:
        raise AuthorizationError(
            "Actor is not authorized to validate the mission for the user"
        )

    if user:
        activities_to_validate = mission.activities_for(user)
    else:
        activities_to_validate = mission.acknowledged_activities

    if not activities_to_validate:
        raise NoActivitiesToValidateError(
            "There are no activities in the validation scope."
        )

    if any([not a.end_time for a in activities_to_validate]):
        raise MissionStillRunningError()

    users = set([a.user for a in activities_to_validate])

    for u in users:
        if not mission.ended_for(u):
            db.session.add(
                MissionEnd(
                    submitter=submitter,
                    reception_time=validation_time,
                    user=u,
                    mission=mission,
                )
            )

    return _get_or_create_validation(
        mission,
        submitter,
        user,
        is_admin=is_admin_validation,
        validation_time=validation_time,
    )


def _get_or_create_validation(
    mission, submitter, user, is_admin, validation_time=None
):
    existing_validation = MissionValidation.query.filter(
        MissionValidation.mission_id == mission.id,
        MissionValidation.submitter_id == submitter.id,
        MissionValidation.user_id == (user.id if user else None),
    ).one_or_none()

    if existing_validation:
        return existing_validation
    else:
        validation = MissionValidation(
            submitter=submitter,
            mission=mission,
            user=user,
            reception_time=validation_time or datetime.now(),
            is_admin=is_admin,
        )
        db.session.add(validation)
        return validation
