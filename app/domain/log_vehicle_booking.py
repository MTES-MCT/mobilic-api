from app import db
from app.domain.log_events import check_whether_event_should_not_be_logged
from app.models import VehicleBooking


def log_vehicle_booking(registration_number, user_time, event_time, submitter):
    if check_whether_event_should_not_be_logged(
        submitter=submitter,
        event_time=event_time,
        registration_number=registration_number,
        event_history=submitter.submitted_vehicle_bookings,
    ):
        return

    db.session.add(
        VehicleBooking(
            registration_number=registration_number,
            user_time=user_time,
            event_time=event_time,
            submitter=submitter,
            company_id=submitter.company_id,
        )
    )
