import graphene
from graphene.types.generic import GenericScalar
from datetime import datetime

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.log_activities import log_activity
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import TimeStamp
from app.models.activity import ActivityType
from app.models.mission import Mission
from app.models import Company, Vehicle
from app.models.mission_validation import MissionValidation
from app.data_access.mission import MissionOutput
from app.domain.permissions import (
    can_user_log_on_mission_at,
    belongs_to_company_at,
)
from app.helpers.authentication import current_user
from app.models.queries import (
    user_query_with_activities,
    mission_query_with_activities,
)
from app.helpers.errors import AuthorizationError


class MissionInput:
    name = graphene.Argument(
        graphene.String,
        required=False,
        description="Nom optionnel de la mission",
    )
    company_id = graphene.Argument(
        graphene.Int,
        required=False,
        description="Optionnel, précise l'entreprise qui effectue la mission. Par défaut c'est l'entreprise de l'auteur de l'opération.",
    )
    context = graphene.Argument(
        GenericScalar,
        required=False,
        description="Informations de contexte de la mission, sous la forme d'un dictionnaire de données libre",
    )


class CreateMission(graphene.Mutation):
    """
    Création d'une nouvelle mission, dans laquelle pourront être enregistrés des activités et des frais.

    Retourne la mission créée.
    """

    Arguments = MissionInput

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **mission_input):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Creating a new mission with name {mission_input.get('name')}"
            )
            # Preload resources
            company_id = mission_input.get("company_id")
            if company_id:
                company = Company.query.get(company_id)
                if not belongs_to_company_at(current_user, company):
                    raise AuthorizationError(
                        f"User is not authorized to create a mission for company {company}"
                    )

            else:
                company = current_user.primary_company

            context = mission_input.get("context")

            if (
                context
                and context.get("vehicleRegistrationNumber")
                and not context.get("vehicleId")
            ):
                registration_number = context.get("vehicleRegistrationNumber")
                vehicle = Vehicle.query.filter(
                    Vehicle.registration_number == registration_number,
                    Vehicle.company_id == company.id,
                ).one_or_none()

                if not vehicle:
                    vehicle = Vehicle(
                        registration_number=registration_number,
                        submitter=current_user,
                        company=company,
                    )
                    db.session.add(vehicle)
                    db.session.flush()  # To get a DB id for the new vehicle

                context.pop("vehicleRegistrationNumber")
                context["vehicleId"] = vehicle.id

            mission = Mission(
                name=mission_input.get("name"),
                company=company,
                reception_time=datetime.now(),
                context=context,
                submitter=current_user,
            )
            db.session.add(mission)

        return mission


class EndMission(graphene.Mutation):
    """
    Fin de la mission, qui mettra un terme à l'activité la plus récente enregistrée pour la mission.

    Retourne la mission.
    """

    class Arguments:
        mission_id = graphene.Int(
            required=True, description="Identifiant de la mission à terminer"
        )
        end_time = graphene.Argument(
            TimeStamp,
            required=True,
            description="Horodatage de fin de mission.",
        )
        context = GenericScalar(
            required=False,
            description="Commentaire libre sur la fin de mission",
        )
        user_id = graphene.Int(
            required=False,
            description="Optionnel, identifiant du travailleur mobile concerné par la fin de la mission. Par défaut c'est l'auteur de l'opération.",
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **args):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            mission = mission_query_with_activities().get(
                args.get("mission_id")
            )

            user_id = args.get("user_id")
            if user_id:
                user = user_query_with_activities().get(user_id)
            else:
                user = current_user

            app.logger.info(f"Ending mission {mission}")
            log_activity(
                submitter=current_user,
                user=user,
                mission=mission,
                type=ActivityType.REST,
                reception_time=reception_time,
                start_time=args["end_time"],
                context=args.get("context"),
            )

        return mission


class ValidateMission(graphene.Mutation):
    """
    Validation du contenu (activités + frais) de la mission.

    Retourne la mission.
    """

    class Arguments:
        mission_id = graphene.Int(
            required=True, description="Identifiant de la mission à valider"
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(
        can_user_log_on_mission_at,
        get_target_from_args=lambda *args, **kwargs: Mission.query.get(
            kwargs["mission_id"]
        ),
    )
    def mutate(cls, _, info, mission_id):
        with atomic_transaction(commit_at_end=True):
            mission = Mission.query.get(mission_id)

            db.session.add(
                MissionValidation(
                    submitter=current_user,
                    reception_time=datetime.now(),
                    mission=mission,
                )
            )

        return mission
