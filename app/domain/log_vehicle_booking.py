from app import app, db
from app.domain.log_events import check_whether_event_should_not_be_logged
from app.models import VehicleBooking, Vehicle


def log_vehicle_booking(
    vehicle_id, registration_number, user_time, event_time, submitter
):
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

    if check_whether_event_should_not_be_logged(
        submitter=submitter,
        event_time=event_time,
        vehicle_id=vehicle_id,
        event_history=submitter.submitted_vehicle_bookings,
    ):
        return

    db.session.add(
        VehicleBooking(
            vehicle_id=vehicle_id,
            user_time=user_time,
            event_time=event_time,
            submitter=submitter,
        )
    )
