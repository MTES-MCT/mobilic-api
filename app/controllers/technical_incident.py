import graphene

from app import db
from app.controllers.utils import atomic_transaction
from app.data_access.technical_incident import TechnicalIncidentOutput
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

MAX_DESCRIPTION_LENGTH = 2000


def controller_or_admin_or_bizdev(user):
    return controller_only(user) or admin_or_bizdev(user)


def _validate_period(start_time, end_time):
    if end_time is not None and end_time < start_time:
        raise InvalidParamsError(
            "La date de fin doit être postérieure à la date de début"
        )


def _clean_description(description):
    description = (description or "").strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise InvalidParamsError(
            f"La description ne doit pas dépasser {MAX_DESCRIPTION_LENGTH} "
            "caractères"
        )
    return description or None


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
        _validate_period(start_time, end_time)

        with atomic_transaction(commit_at_end=True):
            incident = TechnicalIncident(
                technical_type=technical_type,
                start_time=start_time,
                end_time=end_time,
                description=_clean_description(description),
            )
            db.session.add(incident)

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
    ):
        incident = TechnicalIncident.query.get(incident_id)
        if not incident:
            raise InvalidParamsError("Dysfonctionnement introuvable")

        new_start = (
            start_time if start_time is not None else incident.start_time
        )
        new_end = end_time if end_time is not None else incident.end_time
        _validate_period(new_start, new_end)

        with atomic_transaction(commit_at_end=True):
            if technical_type is not None:
                incident.technical_type = technical_type
            if start_time is not None:
                incident.start_time = start_time
            if end_time is not None:
                incident.end_time = end_time
            if description is not None:
                incident.description = _clean_description(description)

        return incident


class ResolveTechnicalIncident(AuthenticatedMutation):
    """Clôture un dysfonctionnement technique en fixant sa date de fin."""

    class Arguments:
        incident_id = graphene.Int(required=True)
        end_time = TimeStamp(required=True)

    Output = TechnicalIncidentOutput

    @classmethod
    @with_authorization_policy(admin_or_bizdev)
    def mutate(cls, _, info, incident_id, end_time):
        incident = TechnicalIncident.query.get(incident_id)
        if not incident:
            raise InvalidParamsError("Dysfonctionnement introuvable")
        _validate_period(incident.start_time, end_time)

        with atomic_transaction(commit_at_end=True):
            incident.end_time = end_time

        return incident


class TechnicalIncidents(graphene.ObjectType):
    create_technical_incident = CreateTechnicalIncident.Field()
    update_technical_incident = UpdateTechnicalIncident.Field()
    resolve_technical_incident = ResolveTechnicalIncident.Field()


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
