import graphene

from app.controllers.comment import LogComment
from app.controllers.mission import BeginMission, EndMission
from app.controllers.vehicle import (
    CreateVehicle,
    EditVehicle,
    TerminateVehicle,
)
from app.controllers.vehicle_booking import LogVehicleBooking
from app.helpers.authentication import AuthMutation
from app.controllers.activity import LogActivity, EditActivity
import app.controllers.user
import app.controllers.company


class Mutations(graphene.ObjectType):
    auth = graphene.Field(
        AuthMutation, resolver=lambda root, info: AuthMutation()
    )
    log_activity = LogActivity.Field()
    log_comment = LogComment.Field()
    begin_mission = BeginMission.Field()
    end_mission = EndMission.Field()
    book_vehicle = LogVehicleBooking.Field()
    signup_user = user.UserSignup.Field()
    signup_company = company.CompanySignup.Field()
    edit_activity = EditActivity.Field()
    create_vehicle = CreateVehicle.Field()
    edit_vehicle = EditVehicle.Field()
    terminate_vehicle = TerminateVehicle.Field()


class Query(user.Query, company.Query, graphene.ObjectType):
    pass


graphql_schema = graphene.Schema(query=Query, mutation=Mutations)
