import graphene

from app.helpers.graphene_types import DateTimeWithTimeStampSerialization


class TeamChange(graphene.ObjectType):
    is_enrollment = graphene.Field(graphene.Boolean)
    user_time = graphene.Field(DateTimeWithTimeStampSerialization)
    coworker = graphene.Field(lambda: UserOutput)
    mission_id = graphene.Field(graphene.Int)


from app.data_access.user import UserOutput
