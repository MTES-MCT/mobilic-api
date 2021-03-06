from app.domain.expenditure import log_expenditure
from app.domain.permissions import can_user_log_on_mission_at
from app.helpers.authentication import current_user
import graphene
from datetime import datetime

from app import app, db
from app.controllers.utils import atomic_transaction, Void
from app.helpers.errors import (
    AuthorizationError,
    ResourceAlreadyDismissedError,
)
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated_and_active,
)
from app.helpers.graphene_types import graphene_enum_type
from app.models import User, Mission
from app.models.expenditure import (
    ExpenditureType,
    ExpenditureOutput,
    Expenditure,
)


class ExpenditureInput:
    type = graphene.Argument(
        graphene_enum_type(ExpenditureType),
        required=True,
        description="Type de frais",
    )
    mission_id = graphene.Int(
        required=True,
        description="Identifiant de la mission à laquelle se rattache le frais",
    )
    user_id = graphene.Int(
        required=False,
        description="Optionnel, identifiant du travailleur concerné par le frais. Par défaut c'est l'auteur de l'opération.",
    )


class LogExpenditure(graphene.Mutation):
    """
    Enregistrement d'un frais.

    Retourne le frais nouvellement créé.
    """

    Arguments = ExpenditureInput

    Output = ExpenditureOutput

    @classmethod
    @with_authorization_policy(authenticated_and_active)
    def mutate(cls, _, info, **expenditure_input):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            app.logger.info(
                f"Logging expenditure submitted by {current_user} of company {current_user.primary_company}"
            )
            mission_id = expenditure_input.get("mission_id")
            mission = Mission.query.get(mission_id)

            user_id = expenditure_input.get("user_id")
            if user_id:
                user = User.query.get(user_id)
                if not user:
                    raise AuthorizationError("Forbidden access")
            else:
                user = current_user

            expenditure = log_expenditure(
                submitter=current_user,
                user=user,
                mission=mission,
                type=expenditure_input["type"],
                reception_time=reception_time,
            )

        return expenditure


class CancelExpenditure(graphene.Mutation):
    """
    Annulation d'un frais.

    Retourne un message de succès.
    """

    class Arguments:
        expenditure_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant du frais à annuler",
        )

    Output = Void

    @classmethod
    @with_authorization_policy(authenticated_and_active)
    def mutate(cls, _, info, expenditure_id):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            expenditure_to_dismiss = Expenditure.query.get(expenditure_id)

            if not expenditure_to_dismiss:
                raise AuthorizationError(
                    "Actor is not authorized to dismiss the expenditure"
                )

            mission = Mission.query.get(expenditure_to_dismiss.mission_id)

            if not can_user_log_on_mission_at(
                current_user, mission, expenditure_to_dismiss.reception_time
            ):
                raise AuthorizationError(
                    "Actor is not authorized to dismiss the expenditure"
                )

            if expenditure_to_dismiss.is_dismissed:
                raise ResourceAlreadyDismissedError(
                    "Expenditure already dismissed"
                )

            db.session.add(expenditure_to_dismiss)
            app.logger.info(f"Cancelling {expenditure_to_dismiss}")
            expenditure_to_dismiss.dismiss(reception_time)

        return Void(success=True)
