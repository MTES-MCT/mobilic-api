import graphene

from app.controllers.comment import CommentLog
from app.controllers.expenditure import ExpenditureLog, CancelExpenditures
from app.controllers.mission import MissionLog
from app.controllers.team_enrollment import TeamEnrollmentLog
from app.helpers.authentication import AuthMutation
from app.controllers.activity import (
    ActivityLog,
    CancelActivities,
    ReviseActivities,
)
import app.controllers.user
import app.controllers.company


class Mutations(graphene.ObjectType):
    auth = graphene.Field(
        AuthMutation, resolver=lambda root, info: AuthMutation()
    )
    log_activities = ActivityLog.Field()
    log_expenditures = ExpenditureLog.Field()
    log_comments = CommentLog.Field()
    log_team_enrollments = TeamEnrollmentLog.Field()
    log_missions = MissionLog.Field()
    signup_user = user.UserSignup.Field()
    signup_company = company.CompanySignup.Field()
    cancel_expenditures = CancelExpenditures.Field()
    cancel_activities = CancelActivities.Field()
    revise_activities = ReviseActivities.Field()


class Query(user.Query, company.Query, graphene.ObjectType):
    pass


graphql_schema = graphene.Schema(query=Query, mutation=Mutations)
