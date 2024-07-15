from datetime import datetime, timedelta

from app import db
from app.domain.mission import get_mission_start_and_end_from_activities
from app.domain.permissions import company_admin
from app.domain.regulations import compute_regulations
from app.domain.user import get_current_employment_in_company
from app.helpers.authorization import AuthorizationError
from app.helpers.errors import (
    MissionNotAlreadyValidatedByUserError,
    NoActivitiesToValidateError,
    MissionStillRunningError,
)
from app.helpers.submitter_type import SubmitterType
from app.models import MissionValidation, MissionEnd

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

    # Special case #1 - mission started more than 10d ago
    mission_start = activities_to_validate[0].start_time
    mission_old_enough = (
        datetime.now() - mission_start
        > MIN_MISSION_LIFETIME_FOR_ADMIN_FORCE_VALIDATION
    )
    if mission_old_enough:
        return

    # Special case #2 - last activity started more than 24h ago and still running
    last_activity_start = activities_to_validate[-1].start_time
    last_activity_is_running = not activities_to_validate[-1].end_time
    last_activity_long_enough = (
        datetime.now() - last_activity_start
        > MIN_LAST_ACTIVITY_LIFETIME_FOR_ADMIN_FORCE_VALIDATION
    )
    if last_activity_long_enough and last_activity_is_running:
        return

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
        employment = get_current_employment_in_company(
            user=for_user, company=mission.company
        )
        _compute_regulations_after_validation(
            activities_to_validate,
            is_admin_validation,
            for_user,
            business=employment.business if employment else None,
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
    activities_to_validate, is_admin_validation, user, business=None
):
    mission_start, mission_end = get_mission_start_and_end_from_activities(
        activities=activities_to_validate, user=user
    )
    submitter_type = (
        SubmitterType.ADMIN if is_admin_validation else SubmitterType.EMPLOYEE
    )
    compute_regulations(
        user=user,
        period_start=mission_start,
        period_end=mission_end,
        submitter_type=submitter_type,
        business=business,
    )
