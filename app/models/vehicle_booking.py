from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.event import DeferrableEventBaseModel


class VehicleBooking(DeferrableEventBaseModel):
    backref_base_name = "vehicle_bookings"

    registration_number = db.Column(db.TEXT, nullable=False)


class VehicleBookingOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = VehicleBooking
