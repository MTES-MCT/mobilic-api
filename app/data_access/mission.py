import graphene

from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.helpers.authentication import current_user
from app.models import Mission
from app.models.activity import ActivityOutput
from app.models.expenditure import ExpenditureOutput


class MissionOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Mission

    activities = graphene.List(ActivityOutput)
    expenditures = graphene.List(ExpenditureOutput)
    validated = graphene.Field(graphene.Boolean)

    def resolve_activities(self, info):
        return self.acknowledged_activities

    def resolve_expenditures(self, info):
        return self.acknowledged_expenditures

    def resolve_validated(self, info):
        user = getattr(info.context, "user_being_queried", current_user)
        return self.validated_by(user)
