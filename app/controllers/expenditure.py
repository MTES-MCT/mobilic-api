from app.domain.expenditure import log_expenditure
from app.domain.permissions import can_user_log_on_mission_at
from app.helpers.authentication import current_user
import graphene
from sqlalchemy.exc import IntegrityError, DatabaseError
from datetime import datetime

from app import app, db
from app.controllers.utils import atomic_transaction
from app.helpers.errors import (
    AuthorizationError,
    ResourceAlreadyDismissedError,
    DuplicateExpendituresError,
    InternalError,
)
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated_and_active,
)
from app.helpers.graphene_types import graphene_enum_type
from app.models import User
from app.models.event import DismissType
from app.models.expenditure import (
    ExpenditureType,
    ExpenditureOutput,
    Expenditure,
)
from app.models.queries import mission_query_with_relations


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

    Retourne la liste des frais de la mission.
    """

    Arguments = ExpenditureInput

    Output = graphene.List(ExpenditureOutput)

    @classmethod
    @with_authorization_policy(authenticated_and_active)
    def mutate(cls, _, info, **expenditure_input):
        try:
            with atomic_transaction(commit_at_end=True):
                reception_time = datetime.now()
                app.logger.info(
                    f"Logging expenditure submitted by {current_user} of company {current_user.primary_company}"
                )
                mission_id = expenditure_input.get("mission_id")
                mission = mission_query_with_relations().get(mission_id)

                user_id = expenditure_input.get("user_id")
                if user_id:
                    user = User.query.get(user_id)
                    if not user:
                        raise AuthorizationError("Unauthorized access")
                else:
                    user = current_user

                log_expenditure(
                    submitter=current_user,
                    user=user,
                    mission=mission,
                    type=expenditure_input["type"],
                    reception_time=reception_time,
                )

        except IntegrityError as e:
            app.logger.exception(e)
            raise DuplicateExpendituresError(
                "An expenditure of that type is already logged for the user on the mission"
            )

        except DatabaseError as e:
            app.logger.exception(e)
            raise InternalError("An internal error occurred")

        return mission.acknowledged_expenditures


class CancelExpenditure(graphene.Mutation):
    """
        Annulation d'un frais.

        Retourne la liste des frais de la mission.
    """

    class Arguments:
        expenditure_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant du frais à annuler",
        )

    Output = graphene.List(ExpenditureOutput)

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

            mission = mission_query_with_relations().get(
                expenditure_to_dismiss.mission_id
            )

            if not can_user_log_on_mission_at(
                current_user, mission, expenditure_to_dismiss.reception_time
            ):
                raise AuthorizationError(
                    "Actor is not authorized to dismiss the expenditure"
                )

            if not expenditure_to_dismiss.is_acknowledged:
                raise ResourceAlreadyDismissedError(
                    "Expenditure already dismissed"
                )

            db.session.add(expenditure_to_dismiss)
            app.logger.info(f"Cancelling {expenditure_to_dismiss}")
            expenditure_to_dismiss.dismiss(
                DismissType.USER_CANCEL, reception_time
            )

        return mission.acknowledged_expenditures
