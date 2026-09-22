import graphene

from app.controllers.utils import atomic_transaction
from app.data_access.technical_incident import TechnicalIncidentOutput
from app.domain.technical_incident import (
    create_incident,
    update_incident,
)
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import (
    admin_or_bizdev,
    controller_only,
    with_authorization_policy,
)
from app.helpers.errors import InvalidParamsError
from app.helpers.graphene_types import (
    TimeStamp,
    graphene_enum_type,
)
from app.models.technical_incident import (
    TechnicalIncident,
    TechnicalIncidentType,
)


def controller_or_admin_or_bizdev(user):
    return controller_only(user) or admin_or_bizdev(user)


class CreateTechnicalIncident(AuthenticatedMutation):
    """Enregistre un dysfonctionnement technique dans le registre."""

    class Arguments:
        technical_type = graphene.Argument(
            graphene_enum_type(TechnicalIncidentType), required=True
        )
        start_time = TimeStamp(required=True)
        end_time = TimeStamp(required=False)
        description = graphene.String(required=False)

    Output = TechnicalIncidentOutput

    @classmethod
    @with_authorization_policy(admin_or_bizdev)
    def mutate(
        cls,
        _,
        info,
        technical_type,
        start_time,
        end_time=None,
        description=None,
    ):
        with atomic_transaction(commit_at_end=True):
            incident = create_incident(
                technical_type=technical_type,
                start_time=start_time,
                end_time=end_time,
                description=description,
            )

        return incident


class UpdateTechnicalIncident(AuthenticatedMutation):
    """Met à jour un dysfonctionnement technique existant."""

    class Arguments:
        incident_id = graphene.Int(required=True)
        technical_type = graphene.Argument(
            graphene_enum_type(TechnicalIncidentType), required=False
        )
        start_time = TimeStamp(required=False)
        end_time = TimeStamp(required=False)
        description = graphene.String(required=False)
        reopen = graphene.Boolean(
            required=False,
            description="Rouvre un dysfonctionnement clôturé en supprimant "
            "sa date de fin. Incompatible avec end_time.",
        )

    Output = TechnicalIncidentOutput

    @classmethod
    @with_authorization_policy(admin_or_bizdev)
    def mutate(
        cls,
        _,
        info,
        incident_id,
        technical_type=None,
        start_time=None,
        end_time=None,
        description=None,
        reopen=False,
    ):
        incident = TechnicalIncident.query.get(incident_id)
        if not incident:
            raise InvalidParamsError("Dysfonctionnement introuvable")

        if reopen and end_time is not None:
            raise InvalidParamsError(
                "Impossible de fournir une date de fin et de rouvrir "
                "le dysfonctionnement en même temps."
            )

        changes = {}
        if technical_type is not None:
            changes["technical_type"] = technical_type
        if start_time is not None:
            changes["start_time"] = start_time
        if reopen:
            changes["end_time"] = None
        elif end_time is not None:
            changes["end_time"] = end_time
        if description is not None:
            changes["description"] = description

        with atomic_transaction(commit_at_end=True):
            update_incident(incident, **changes)

        return incident


class TechnicalIncidents(graphene.ObjectType):
    create_technical_incident = CreateTechnicalIncident.Field()
    update_technical_incident = UpdateTechnicalIncident.Field()


class Query(graphene.ObjectType):
    technical_incidents = graphene.List(
        TechnicalIncidentOutput,
        description="Registre des dysfonctionnements techniques connus, "
        "du plus récent au plus ancien.",
    )

    @with_authorization_policy(controller_or_admin_or_bizdev)
    def resolve_technical_incidents(self, info):
        return TechnicalIncident.query.order_by(
            TechnicalIncident.start_time.desc()
        ).all()
