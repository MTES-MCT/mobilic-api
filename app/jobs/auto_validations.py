from datetime import datetime, timedelta

from jours_feries_france import JoursFeries
from sqlalchemy.orm import selectinload

from app import app, db
from app.domain.validation import validate_mission
from app.jobs import log_execution
from app.models import MissionAutoValidation

EMPLOYEE_THRESHOLD_HOURS = 24
ADMIN_THRESHOLD_DAYS = 2


def get_employee_auto_validations(now):
    threshold_time = now - timedelta(hours=EMPLOYEE_THRESHOLD_HOURS)
    auto_validations = (
        MissionAutoValidation.query.options(
            selectinload(MissionAutoValidation.user),
            selectinload(MissionAutoValidation.mission),
        )
        .filter(
            MissionAutoValidation.reception_time < threshold_time,
            MissionAutoValidation.is_admin == False,
        )
        .all()
    )
    return auto_validations


def get_admin_auto_validations(now):
    threshold_time = now
    days_to_remove = ADMIN_THRESHOLD_DAYS
    while days_to_remove > 0:
        threshold_time -= timedelta(days=1)
        if threshold_time.weekday() < 5 and not JoursFeries.is_bank_holiday(
            threshold_time.date()
        ):
            days_to_remove -= 1

    auto_validations = (
        MissionAutoValidation.query.options(
            selectinload(MissionAutoValidation.user),
            selectinload(MissionAutoValidation.mission),
        )
        .filter(
            MissionAutoValidation.reception_time < threshold_time,
            MissionAutoValidation.is_admin == True,
        )
        .all()
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
                app.logger.warning(f"Could not auto validate mission: {e}")
                ids_to_delete.append(auto_validation.id)
                continue

    with atomic_transaction(commit_at_end=True):
        ids_to_delete = []

        employee_auto_validations = get_employee_auto_validations(now=now)
        app.logger.info(
            f"Found #{len(employee_auto_validations)} employee auto validations"
        )

        _process_auto_validations(
            auto_validations=employee_auto_validations, is_admin=False
        )

        admin_auto_validations = get_admin_auto_validations(now=now)
        app.logger.info(
            f"Found #{len(admin_auto_validations)} admin auto validations"
        )

        _process_auto_validations(
            auto_validations=admin_auto_validations, is_admin=True
        )

        db.session.query(MissionAutoValidation).filter(
            MissionAutoValidation.id.in_(ids_to_delete)
        ).delete(synchronize_session=False)
