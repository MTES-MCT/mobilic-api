from datetime import datetime

from app import db, app
from app.domain.permissions import company_admin
from app.domain.regulations import compute_regulations
from app.helpers.errors import (
    NoActivitiesToValidateError,
    MissionStillRunningError,
)
from app.helpers.submitter_type import SubmitterType
from app.models import MissionValidation, MissionEnd
from app.helpers.authorization import AuthorizationError


def validate_mission(mission, submitter, creation_time=None, for_user=None):
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
                    creation_time=creation_time,
                )
            )

    mission_start = activities_to_validate[0].start_time.date()
    mission_end = (
        activities_to_validate[-1].end_time.date()
        if activities_to_validate[-1].end_time
        else None
    )
    submitter_type = (
        SubmitterType.ADMIN if is_admin_validation else SubmitterType.EMPLOYEE
    )
    # TODO #613 should we add previous and next day to period?
    compute_regulations(
        user=for_user,
        period_start=mission_start,
        period_end=mission_end,
        submitter_type=submitter_type,
    )

    return _get_or_create_validation(
        mission,
        submitter,
        user,
        is_admin=is_admin_validation,
        validation_time=validation_time,
        creation_time=creation_time,
    )


def _get_or_create_validation(
    mission,
    submitter,
    user,
    is_admin,
    validation_time=None,
    creation_time=None,
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
            creation_time=creation_time,
        )
        db.session.add(validation)
        return validation
