from datetime import datetime, timedelta

from dateutil.tz import gettz

from app import db, app
from app.domain.permissions import company_admin
from app.domain.regulations import compute_regulations
from app.helpers.errors import (
    MissionNotAlreadyValidatedByUserError,
    NoActivitiesToValidateError,
    MissionStillRunningError,
)
from app.helpers.submitter_type import SubmitterType
from app.helpers.time import to_tz
from app.models import MissionValidation, MissionEnd
from app.helpers.authorization import AuthorizationError

MIN_MISSION_LIFETIME_FOR_ADMIN_FORCE_VALIDATION = timedelta(days=10)
MIN_LAST_ACTIVITY_LIFETIME_FOR_ADMIN_FORCE_VALIDATION = timedelta(hours=24)


# In case an admin wants to validate a mission for an employee who did not yet validate its mission
# He should not be able to do it, except for two special cases
def pre_check_validate_mission_by_admin(mission, admin_submitter, for_user):
    activities_to_validate = mission.activities_for(for_user)

    # Checks if employee has already validated its mission
    if len(mission.validations_for(for_user)) > 0:
        return

    # Evacuates case where admin is validating for himself
    if (
        for_user.id == admin_submitter.id
        or mission.submitter_id == admin_submitter.id
    ):
        return

    mission_start = activities_to_validate[0].start_time
    last_activity_start = activities_to_validate[-1].start_time
    mission_old_enough = (
        datetime.now() - mission_start
        > MIN_MISSION_LIFETIME_FOR_ADMIN_FORCE_VALIDATION
    )
    last_activity_long_enough = (
        datetime.now() - last_activity_start
        > MIN_LAST_ACTIVITY_LIFETIME_FOR_ADMIN_FORCE_VALIDATION
    )
    if not (mission_old_enough or last_activity_long_enough):
        raise MissionNotAlreadyValidatedByUserError()


def validate_mission(mission, submitter, for_user, creation_time=None):
    validation_time = datetime.now()
    is_admin_validation = company_admin(submitter, mission.company_id)

    if not is_admin_validation and for_user.id != submitter.id:
        raise AuthorizationError(
            "Actor is not authorized to validate the mission for the user"
        )

    activities_to_validate = mission.activities_for(for_user)

    if not activities_to_validate:
        raise NoActivitiesToValidateError(
            "There are no activities in the validation scope."
        )

    if any([not a.end_time for a in activities_to_validate]):
        raise MissionStillRunningError()

    if not mission.ended_for(for_user):
        db.session.add(
            MissionEnd(
                submitter=submitter,
                reception_time=validation_time,
                user=for_user,
                mission=mission,
                creation_time=creation_time,
            )
        )

    validation = _get_or_create_validation(
        mission,
        submitter,
        for_user,
        is_admin=is_admin_validation,
        validation_time=validation_time,
        creation_time=creation_time,
    )

    if not mission.is_holiday():
        _compute_regulations_after_validation(
            activities_to_validate, is_admin_validation, for_user
        )

    return validation


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


def _compute_regulations_after_validation(
    activities_to_validate, is_admin_validation, user
):
    user_timezone = gettz(user.timezone_name)
    mission_start = to_tz(
        activities_to_validate[0].start_time, user_timezone
    ).date()
    mission_end = (
        to_tz(activities_to_validate[-1].end_time, user_timezone).date()
        if to_tz(activities_to_validate[-1].end_time, user_timezone)
        else None
    )
    submitter_type = (
        SubmitterType.ADMIN if is_admin_validation else SubmitterType.EMPLOYEE
    )
    compute_regulations(
        user=user,
        period_start=mission_start,
        period_end=mission_end,
        submitter_type=submitter_type,
    )
