import graphene

from app.helpers.authentication import AuthMutation
from app.controllers.activity import ActivityLog
import app.controllers.user
import app.controllers.company


class Mutations(graphene.ObjectType):
    auth = graphene.Field(
        AuthMutation, resolver=lambda root, info: AuthMutation()
    )
    log_activities = ActivityLog.Field()
    signup_user = user.UserSignup.Field()
    signup_company = company.CompanySignup.Field()


class Query(user.Query, company.Query, graphene.ObjectType):
    pass


graphql_schema = graphene.Schema(query=Query, mutation=Mutations)
