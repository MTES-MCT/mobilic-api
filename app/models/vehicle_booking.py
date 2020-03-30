import graphene

from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.event import DeferrableEventBaseModel


class VehicleBooking(DeferrableEventBaseModel):
    backref_base_name = "vehicle_bookings"

    vehicle_id = db.Column(
        db.Integer, db.ForeignKey("vehicle.id"), index=True, nullable=False
    )
    vehicle = db.relationship("Vehicle", backref="bookings")


class VehicleBookingOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = VehicleBooking

    vehicle_name = graphene.Field(graphene.String)

    def resolve_vehicle_name(self, info):
        return self.vehicle.name
