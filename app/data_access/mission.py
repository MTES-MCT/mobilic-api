import graphene

from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.helpers.authentication import current_user
from app.models import Mission
from app.models.activity import ActivityOutput
from app.models.comment import CommentOutput
from app.models.vehicle_booking import VehicleBookingOutput


class MissionOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Mission

    activities = graphene.List(ActivityOutput)
    comments = graphene.List(CommentOutput)
    vehicle_bookings = graphene.List(VehicleBookingOutput)

    def resolve_activities(self, info):
        user = getattr(info.context, "user_being_queried", current_user)
        return self.activities_for(user)

    def resolve_comments(self, info):
        return self.comments

    def resolve_vehicle_bookings(self, info):
        return self.vehicle_bookings
