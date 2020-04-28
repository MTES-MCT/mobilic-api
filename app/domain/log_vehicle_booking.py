from app import app, db
from app.domain.log_events import check_whether_event_should_be_logged
from app.domain.permissions import can_submitter_log_on_mission
from app.helpers.authentication import AuthorizationError
from app.models import VehicleBooking, Vehicle


def log_vehicle_booking(
    vehicle_id, registration_number, mission, user_time, event_time, submitter
):
    if not can_submitter_log_on_mission(submitter, mission):
        raise AuthorizationError(
            f"The user is not authorized to log for this mission"
        )

    if not vehicle_id and not registration_number:
        app.logger.warning(
            "Unable to log vehicle booking : neither vehicle id nor registration number were provided"
        )
        return

    if not vehicle_id:
        vehicle = Vehicle(
            registration_number=registration_number,
            submitter=submitter,
            company_id=submitter.company_id,
        )
        db.session.add(vehicle)
        db.session.flush()  # To get a DB id for the new vehicle
        vehicle_id = vehicle.id

    # Check that user current mission corresponds to the passed mission
    if not submitter.mission_at(user_time) == mission:
        raise AuthorizationError(f"Event is submitted from unauthorized user")

    check_whether_event_should_be_logged(
        submitter=submitter,
        event_time=event_time,
        vehicle_id=vehicle_id,
        event_history=submitter.submitted_vehicle_bookings,
    )

    db.session.add(
        VehicleBooking(
            vehicle_id=vehicle_id,
            user_time=user_time,
            mission=mission,
            event_time=event_time,
            submitter=submitter,
        )
    )
