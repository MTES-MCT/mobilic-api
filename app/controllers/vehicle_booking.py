from app.helpers.authentication import current_user
from sqlalchemy.orm import selectinload
import graphene

from app import app
from app.controllers.utils import atomic_transaction
from app.domain.log_vehicle_booking import log_vehicle_booking
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import DateTimeWithTimeStampSerialization
from app.models import Mission
from app.models.user import User
from app.controllers.event import EventInput
from app.models.vehicle import VehicleOutput
from app.models.vehicle_booking import VehicleBookingOutput


def _preload_db_resources():
    User.query.options(selectinload(User.submitted_vehicle_bookings)).options(
        selectinload(User.company)
    ).filter(User.id == current_user.id).one()


class VehicleBookingInput(EventInput):
    vehicle_id = graphene.Argument(graphene.Int, required=False)
    mission_id = graphene.Argument(graphene.Int, required=False)
    registration_number = graphene.Argument(graphene.String, required=False)
    user_time = graphene.Argument(
        DateTimeWithTimeStampSerialization, required=False
    )


class LogVehicleBooking(graphene.Mutation):
    Arguments = VehicleBookingInput

    vehicle_bookings = graphene.List(VehicleBookingOutput)
    bookable_vehicles = graphene.List(VehicleOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **vehicle_booking_input):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Logging vehicle booking submitted by {current_user} of company {current_user.company}"
            )
            user_time = vehicle_booking_input.get(
                "user_time"
            ) or vehicle_booking_input.get("event_time")
            mission_id = vehicle_booking_input.get("mission_id")
            if not mission_id:
                mission = current_user.mission_at(user_time)
            else:
                mission = Mission.query.get(mission_id)
            _preload_db_resources()
            vehicle_booking = log_vehicle_booking(
                submitter=current_user,
                user_time=user_time,
                mission=mission,
                event_time=vehicle_booking_input.get("event_time"),
                vehicle_id=vehicle_booking_input.get("vehicle_id"),
                registration_number=vehicle_booking_input.get(
                    "registration_number"
                ),
            )

        return LogVehicleBooking(
            vehicle_bookings=mission.vehicle_bookings,
            bookable_vehicles=current_user.bookable_vehicles,
        )
