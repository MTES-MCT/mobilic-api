from app.domain.expenditure import log_expenditure
from app.domain.permissions import check_actor_can_write_on_mission
from app.helpers.authentication import current_user, AuthenticatedMutation
import graphene
from datetime import datetime
from app.helpers.graphene_types import (
    graphene_enum_type,
    TimeStamp,
)
from app import app, db
from app.controllers.utils import atomic_transaction, Void
from app.helpers.errors import (
    AuthorizationError,
    ResourceAlreadyDismissedError,
)
from app.helpers.authorization import (
    with_authorization_policy,
    active,
)
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
    spending_date = graphene.Argument(
        graphene.Date,
        required=True,
        description="Date à laquelle le frais a été engagé.",
    )
    creation_time = graphene.Argument(
        TimeStamp,
        required=False,
        description="Optionnel, date de saisie du frais",
    )


class BulkExpenditureItem(graphene.InputObjectType, ExpenditureInput):
    pass


def log_expenditure_(expenditure_input):
    reception_time = datetime.now()
    mission_id = expenditure_input.get("mission_id")
    mission = Mission.query.get(mission_id)

    user_id = expenditure_input.get("user_id")

    spending_date = expenditure_input.get("spending_date")

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
        spending_date=spending_date,
        creation_time=expenditure_input.get("creation_time"),
    )
    return expenditure


class LogExpenditure(AuthenticatedMutation):
    """
    Enregistrement d'un frais.

    Retourne le frais nouvellement créé.
    """

    Arguments = ExpenditureInput

    Output = ExpenditureOutput

    @classmethod
    @with_authorization_policy(active)
    def mutate(cls, _, info, **expenditure_input):
        with atomic_transaction(commit_at_end=True):
            return log_expenditure_(expenditure_input)


def cancel_expenditure(expenditure_id):
    reception_time = datetime.now()
    expenditure_to_dismiss = Expenditure.query.get(expenditure_id)

    if not expenditure_to_dismiss:
        raise AuthorizationError(
            "Actor is not authorized to dismiss the expenditure"
        )

    mission = Mission.query.get(expenditure_to_dismiss.mission_id)

    check_actor_can_write_on_mission(
        current_user,
        mission,
        for_user=expenditure_to_dismiss.user,
        at=expenditure_to_dismiss.spending_date,
    )

    if expenditure_to_dismiss.is_dismissed:
        raise ResourceAlreadyDismissedError("Expenditure already dismissed")

    db.session.add(expenditure_to_dismiss)
    expenditure_to_dismiss.dismiss(reception_time)


class CancelExpenditure(AuthenticatedMutation):
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
    @with_authorization_policy(active)
    def mutate(cls, _, info, expenditure_id):
        with atomic_transaction(commit_at_end=True):
            cancel_expenditure(expenditure_id)

        return Void(success=True)
