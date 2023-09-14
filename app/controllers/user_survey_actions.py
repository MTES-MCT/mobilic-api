import graphene

from app.helpers.graphene_types import graphene_enum_type
from app.domain.permissions import only_self
from app.domain.user_survey_actions import (
    create_action_for_user,
    get_all_survey_actions_for_user,
)
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import with_authorization_policy
from app.models.user_survey_actions import (
    SurveyAction,
    UserSurveyActionsOutput,
)


class CreateSurveyAction(AuthenticatedMutation):
    class Arguments:
        user_id = graphene.Int(
            required=True,
            description="Identifiant de l'utilisateur",
        )
        survey_id = graphene.String(
            required=True, description="Identifiant du sondage"
        )
        action = graphene.Argument(
            graphene_enum_type(SurveyAction),
            required=True,
            description="action à enregistrer",
        )

    Output = graphene.List(UserSurveyActionsOutput)

    @classmethod
    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda *args, **kwargs: kwargs["user_id"],
        error_message="Forbidden access",
    )
    def mutate(
        cls,
        _,
        info,
        user_id,
        survey_id,
        action,
    ):
        create_action_for_user(
            user_id=user_id, survey_id=survey_id, action=action
        )
        return get_all_survey_actions_for_user(user_id=user_id)
