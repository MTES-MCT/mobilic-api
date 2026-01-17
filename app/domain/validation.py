from datetime import datetime, timedelta

from app import db
from app.domain.mission import (
    get_mission_start_and_end_from_activities,
    end_mission_for_user,
)
from app.domain.permissions import company_admin
from app.domain.regulations import compute_regulations
from app.domain.user import get_current_employment_in_company
from app.helpers.authorization import AuthorizationError
from app.helpers.errors import (
    MissionNotAlreadyValidatedByUserError,
    NoActivitiesToValidateError,
    MissionStillRunningError,
    MissionAlreadyAutoValidatedError,
)
from app.helpers.submitter_type import SubmitterType
from app.models import MissionValidation, MissionEnd, MissionAutoValidation
from app.helpers.notification_type import NotificationType
from app.helpers.time import to_tz
from app.models.notification import create_notification
from dateutil.tz import gettz

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


def validate_mission(
    mission,
    submitter,
    for_user,
    creation_time=None,
    employee_version_start_time=None,
    employee_version_end_time=None,
    is_auto_validation=False,
    is_admin_validation=None,
    justification=None,
):
    validation_time = datetime.now()

    is_admin_validation = (
        is_admin_validation
        if is_admin_validation is not None
        else company_admin(submitter, mission.company_id)
    )

    if not is_auto_validation:
        if not is_admin_validation and for_user.id != submitter.id:
            raise AuthorizationError(
                "Actor is not authorized to validate the mission for the user"
            )
        # Check that employee cannot validate auto-validated missions
        if not is_admin_validation and (
            mission.auto_validated_by_employee_for(for_user)
            or mission.auto_validated_by_admin_for(for_user)
        ):
            raise MissionAlreadyAutoValidatedError()

    activities_to_validate = mission.activities_for(for_user)

    if not activities_to_validate:
        raise NoActivitiesToValidateError(
            "There are no activities in the validation scope."
        )

    if is_auto_validation:
        end_mission_for_user(
            user=for_user, mission=mission, raise_already_ended=False
        )
    else:
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
        None if is_auto_validation else submitter,
        for_user,
        is_admin=is_admin_validation,
        validation_time=validation_time,
        creation_time=creation_time,
        is_auto_validation=is_auto_validation,
        justification=justification,
    )

    if not mission.is_holiday():
        db.session.query(MissionAutoValidation).filter(
            MissionAutoValidation.mission == mission,
            MissionAutoValidation.user == for_user,
        ).delete(synchronize_session=False)
        if not is_admin_validation:
            admin_auto_validation = MissionAutoValidation(
                mission=mission,
                is_admin=True,
                user=for_user,
                reception_time=validation_time,
            )
            db.session.add(admin_auto_validation)

        employment = get_current_employment_in_company(
            user=for_user, company=mission.company
        )
        _compute_regulations_after_validation(
            activities=activities_to_validate,
            is_admin_validation=is_admin_validation,
            user=for_user,
            business=employment.business if employment else None,
            employee_version_start_time=employee_version_start_time,
            employee_version_end_time=employee_version_end_time,
        )

    if not is_admin_validation and is_auto_validation:
        user_timezone = gettz(for_user.timezone_name)

        mission_start_time = (
            activities_to_validate[0].start_time
            if activities_to_validate
            else validation_time
        )

        create_notification(
            user_id=for_user.id,
            notification_type=NotificationType.MISSION_AUTO_VALIDATION,
            data={
                "mission_id": mission.id,
                "mission_name": mission.name,
                "mission_start_date": to_tz(
                    mission_start_time, user_timezone
                ).isoformat(),
            },
        )

    return validation


def _get_or_create_validation(
    mission,
    submitter,
    user,
    is_admin,
    validation_time=None,
    creation_time=None,
    is_auto_validation=False,
    justification=None,
):
    existing_validation = MissionValidation.query.filter(
        MissionValidation.mission_id == mission.id,
        MissionValidation.submitter_id
        == (submitter.id if submitter else None),
        MissionValidation.user_id == (user.id if user else None),
        MissionValidation.is_admin == is_admin,
        MissionValidation.is_auto == is_auto_validation,
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
            is_auto=is_auto_validation,
            justification=justification,
        )
        db.session.add(validation)
        return validation


def _compute_regulations_after_validation(
    activities,
    is_admin_validation,
    user,
    business=None,
    employee_version_start_time=None,
    employee_version_end_time=None,
):
    mission_start, mission_end = get_mission_start_and_end_from_activities(
        activities=activities, user=user
    )

    # Look back 7 days to recalculate multi-day regulatory alerts.
    # This ensures that alerts spanning multiple consecutive days are properly
    # recalculated when validating a new mission. For example, a night work alert
    # covering days D-2, D-1, and D could disappear when validating a new mission
    # on day D if we only recalculate from mission_start.
    REGULATION_LOOKBACK_DAYS = 7
    lookback_start = mission_start - timedelta(days=REGULATION_LOOKBACK_DAYS)

    period_start = (
        min(lookback_start, employee_version_start_time.date())
        if employee_version_start_time
        else lookback_start
    )

    if employee_version_end_time:
        if mission_end:
            period_end = max(mission_end, employee_version_end_time.date())
        else:
            period_end = employee_version_end_time.date()
    else:
        period_end = mission_end or datetime.now().date()

    submitter_type = (
        SubmitterType.ADMIN if is_admin_validation else SubmitterType.EMPLOYEE
    )
    compute_regulations(
        user=user,
        period_start=period_start,
        period_end=period_end,
        submitter_type=submitter_type,
        business=business,
    )
