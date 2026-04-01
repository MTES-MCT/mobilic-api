from datetime import datetime, timedelta

import sentry_sdk
from jours_feries_france import JoursFeries
from sqlalchemy.orm import selectinload

from app import app, db
from app.domain.validation import validate_mission
from app.jobs import log_execution
from app.models import MissionAutoValidation
from app.helpers.errors import (
    NoActivitiesToValidateError,
    MissionAlreadyAutoValidatedError,
)

ADMIN_THRESHOLD_DAYS = 2
EMPLOYEE_THRESHOLD_DAYS = 1
AUTO_VALIDATION_BATCH_SIZE = 400


def _get_threshold_time(now, days_to_remove):
    threshold_time = now
    while days_to_remove > 0:
        threshold_time -= timedelta(days=1)
        if threshold_time.weekday() < 5 and not JoursFeries.is_bank_holiday(
            threshold_time.date()
        ):
            days_to_remove -= 1
    return threshold_time


def _get_auto_validations(threshold_time, is_admin):
    return (
        MissionAutoValidation.query.options(
            selectinload(MissionAutoValidation.user),
            selectinload(MissionAutoValidation.mission),
        )
        .filter(
            MissionAutoValidation.reception_time < threshold_time,
            MissionAutoValidation.is_admin == is_admin,
        )
        .order_by(MissionAutoValidation.reception_time)
        .all()
    )


def get_employee_auto_validations(now):
    threshold_time = _get_threshold_time(
        now=now, days_to_remove=EMPLOYEE_THRESHOLD_DAYS
    )
    app.logger.info(
        f"Employee auto-validation threshold: {threshold_time} (current time: {now})"
    )
    auto_validations = _get_auto_validations(
        threshold_time=threshold_time, is_admin=False
    )
    return auto_validations


def get_admin_auto_validations(now):
    threshold_time = _get_threshold_time(
        now=now, days_to_remove=ADMIN_THRESHOLD_DAYS
    )
    app.logger.info(
        f"Admin auto-validation threshold: {threshold_time} (current time: {now})"
    )

    auto_validations = _get_auto_validations(
        threshold_time=threshold_time, is_admin=True
    )
    return auto_validations


@log_execution
def job_process_auto_validations():
    from app import atomic_transaction

    now = datetime.now()

    def _process_auto_validations(auto_validations, is_admin):
        for auto_validation in auto_validations:
            for_user = auto_validation.user
            mission = auto_validation.mission

            if not for_user:
                app.logger.warning(
                    f"Skipping auto-validation for mission {mission.id}: user not found (deleted?)"
                )
                db.session.delete(auto_validation)
                db.session.commit()
                continue

            app.logger.info(
                f"Processing auto-validation for mission {mission.id}, user {for_user.id}, reception_time {auto_validation.reception_time}"
            )

            try:
                with atomic_transaction(commit_at_end=True):
                    validation = validate_mission(
                        mission=mission,
                        submitter=None,
                        for_user=for_user,
                        creation_time=now,
                        is_auto_validation=True,
                        is_admin_validation=is_admin,
                    )
                    db.session.add(validation)
            except (
                NoActivitiesToValidateError,
                MissionAlreadyAutoValidatedError,
            ) as e:
                app.logger.warning(
                    f"Could not auto validate mission <{mission.id}>: {e} (removing from queue)"
                )
                db.session.delete(auto_validation)
                db.session.commit()
                continue
            except Exception as e:
                with sentry_sdk.new_scope() as scope:
                    scope.fingerprint = [
                        "auto-validation-failure",
                        type(e).__name__,
                    ]
                    scope.set_tag("job", "process_auto_validations")
                    scope.set_tag("is_admin", str(is_admin))
                    scope.set_context(
                        "auto_validation",
                        {
                            "mission_id": mission.id,
                            "user_id": for_user.id,
                            "user_email": for_user.email,
                            "reception_time": str(
                                auto_validation.reception_time
                            ),
                        },
                    )
                    sentry_sdk.capture_exception(e)
                app.logger.error(
                    f"Could not auto validate mission <{mission.id}>: {e} (keeping in queue for retry)"
                )
                continue

    employee_auto_validations = get_employee_auto_validations(now=now)[
        :AUTO_VALIDATION_BATCH_SIZE
    ]
    app.logger.info(
        f"Found #{len(employee_auto_validations)} employee auto validations"
    )

    _process_auto_validations(
        auto_validations=employee_auto_validations, is_admin=False
    )

    admin_auto_validations = get_admin_auto_validations(now=now)[
        :AUTO_VALIDATION_BATCH_SIZE
    ]
    app.logger.info(
        f"Found #{len(admin_auto_validations)} admin auto validations"
    )

    _process_auto_validations(
        auto_validations=admin_auto_validations, is_admin=True
    )
