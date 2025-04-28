from datetime import datetime, timedelta

from app import app, db
from app.domain.validation import validate_mission
from app.jobs import log_execution
from app.models import MissionAutoValidation

THRESHOLD_HOURS = 24


def get_auto_validations(now):
    threshold_time = now - timedelta(hours=THRESHOLD_HOURS)
    auto_validations = MissionAutoValidation.query.filter(
        MissionAutoValidation.reception_time < threshold_time
    ).all()
    return auto_validations


@log_execution
def job_process_auto_validations():
    now = datetime.now()
    auto_validations = get_auto_validations(now=now)
    app.logger.info(f"Found #{len(auto_validations)} auto validations")

    ids_to_delete = []
    for auto_validation in auto_validations:
        app.logger.info(auto_validation)

        for_user = auto_validation.user
        mission = auto_validation.mission

        try:
            validation = validate_mission(
                mission=mission,
                submitter=None,
                for_user=for_user,
                creation_time=now,
                is_auto_validation=True,
            )
        except Exception as e:
            app.logger.warning(f"Could not auto validate mission: {e}")
            ids_to_delete.append(auto_validation.id)
            continue

        db.session.add(validation)

    db.session.query(MissionAutoValidation).filter(
        MissionAutoValidation.id.in_(ids_to_delete)
    ).delete(synchronize_session=False)

    db.session.commit()
