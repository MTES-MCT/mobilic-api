from flask_jwt_extended import current_user
import graphene

from app import app
from app.controllers.event import preload_relevant_resources_for_event_logging
from app.controllers.utils import atomic_transaction
from app.domain.log_vehicle_booking import log_vehicle_booking
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import DateTimeWithTimeStampSerialization
from app.models.user import User
from app.controllers.event import EventInput
from app.models.vehicle import VehicleOutput
from app.models.vehicle_booking import VehicleBookingOutput


class VehicleBookingInput(EventInput):
    vehicle_id = graphene.Field(graphene.Int, required=False)
    registration_number = graphene.Field(graphene.String, required=False)
    user_time = DateTimeWithTimeStampSerialization(required=False)


class VehicleBookingLog(graphene.Mutation):
    class Arguments:
        data = graphene.List(VehicleBookingInput, required=True)

    vehicle_bookings = graphene.List(VehicleBookingOutput)
    bookable_vehicles = graphene.List(VehicleOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Logging vehicle bookings submitted by {current_user} of company {current_user.company}"
            )
            events = sorted(data, key=lambda e: e.event_time)
            preload_relevant_resources_for_event_logging(
                User.submitted_vehicle_bookings
            )
            for vehicle_booking in events:
                log_vehicle_booking(
                    submitter=current_user,
                    user_time=vehicle_booking.user_time
                    or vehicle_booking.event_time,
                    event_time=vehicle_booking.event_time,
                    vehicle_id=vehicle_booking.vehicle_id,
                    registration_number=vehicle_booking.registration_number,
                )

        return VehicleBookingLog(
            vehicle_bookings=current_user.vehicle_bookings,
            bookable_vehicles=current_user.bookable_vehicles,
        )
