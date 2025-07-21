from datetime import datetime, timedelta

from jours_feries_france import JoursFeries
from sqlalchemy.orm import selectinload

from app import app, db
from app.domain.validation import validate_mission
from app.jobs import log_execution
from app.models import MissionAutoValidation

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
    auto_validations = _get_auto_validations(
        threshold_time=threshold_time, is_admin=False
    )
    return auto_validations


def get_admin_auto_validations(now):
    threshold_time = _get_threshold_time(
        now=now, days_to_remove=ADMIN_THRESHOLD_DAYS
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
            except Exception as e:
                app.logger.warning(
                    f"Could not auto validate mission <{mission.id}>: {e}"
                )
                db.session.delete(auto_validation)
                db.session.commit()
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
