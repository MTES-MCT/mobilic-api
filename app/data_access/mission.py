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
    team_changes = graphene.List(lambda: TeamChange)

    def resolve_activities(self, info):
        return self.acknowledged_activities

    def resolve_expenditures(self, info):
        return self.acknowledged_expenditures

    def resolve_validated(self, info):
        user = getattr(info.context, "user_being_queried", current_user)
        return self.validated_by(user)

    def resolve_team_changes(self, info):
        return [
            {**tc, "mission_id": self.id}
            for user_team_changes in self.team_mate_status_history().values()
            for tc in user_team_changes
            if tc["coworker"] != current_user
        ]


from app.data_access.team_change import TeamChange
