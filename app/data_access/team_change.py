import graphene

from app.helpers.graphene_types import TimeStamp


class TeamChange(graphene.ObjectType):
    is_enrollment = graphene.Field(graphene.Boolean)
    time = graphene.Field(TimeStamp)
    coworker = graphene.Field(lambda: UserOutput)
    mission_id = graphene.Field(graphene.Int)


from app.data_access.user import UserOutput
