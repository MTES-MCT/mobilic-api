from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.event import EventBaseModel


class VehicleBooking(EventBaseModel):
    backref_base_name = "vehicle_bookings"

    registration_number = db.Column(db.TEXT, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            "(event_time >= start_time)",
            name="vehicle_booking_start_time_before_event_time",
        ),
    )


class VehicleBookingOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = VehicleBooking
