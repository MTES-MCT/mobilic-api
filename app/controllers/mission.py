import graphene
from graphene.types.generic import GenericScalar
from datetime import datetime
from sqlalchemy.orm import selectinload

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.notifications import (
    warn_if_mission_changes_since_latest_user_action,
)
from app.domain.validation import validate_mission
from app.helpers.authorization import (
    with_authorization_policy,
    active,
)
from app.helpers.graphene_types import TimeStamp
from app.models.mission import Mission
from app.models import Company, Vehicle, User, Activity
from app.models.mission_end import MissionEnd
from app.models.mission_validation import (
    MissionValidationOutput,
)
from app.data_access.mission import MissionOutput
from app.domain.permissions import (
    check_actor_can_write_on_mission,
    is_employed_by_company_over_period,
    can_actor_read_mission,
)
from app.helpers.authentication import current_user, AuthenticatedMutation
from app.helpers.errors import (
    AuthorizationError,
    MissionAlreadyEndedError,
    UnavailableSwitchModeError,
)
from app.models.vehicle import VehicleOutput


def find_or_create_vehicle(vehicle_id, vehicle_registration_number, company):
    if not vehicle_id:
        vehicle = Vehicle.query.filter(
            Vehicle.registration_number == vehicle_registration_number,
            Vehicle.company_id == company.id,
        ).one_or_none()

        if not vehicle:
            vehicle = Vehicle(
                registration_number=vehicle_registration_number,
                submitter=current_user,
                company=company,
            )
            db.session.add(vehicle)
            db.session.flush()  # To get a DB id for the new vehicle

    else:
        vehicle = Vehicle.query.filter(
            Vehicle.id == vehicle_id,
            Vehicle.company_id == company.id,
        ).one_or_none()

    return vehicle


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
    vehicle_id = graphene.Argument(
        graphene.Int,
        required=False,
        description="Identifiant du véhicule utilisé",
    )
    vehicle_registration_number = graphene.Argument(
        graphene.String,
        required=False,
        description="Numéro d'immatriculation du véhicule utilisé, s'il n'est pas déjà enregistré. Un nouveau véhicule sera ajouté.",
    )


class CreateMission(AuthenticatedMutation):
    """
    Création d'une nouvelle mission, dans laquelle pourront être enregistrés des activités et des frais.

    Retourne la mission créée.
    """

    Arguments = MissionInput

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(active)
    def mutate(cls, _, info, **mission_input):
        with atomic_transaction(commit_at_end=True):
            # Preload resources
            company_id = mission_input.get("company_id")
            if company_id:
                company = Company.query.get(company_id)
                if not is_employed_by_company_over_period(
                    current_user, company, include_pending_invite=False
                ):
                    raise AuthorizationError(
                        "Actor is not authorized to create a mission for the company"
                    )

            else:
                company = current_user.primary_company

            if not company:
                raise AuthorizationError("Actor has no primary company")

            context = mission_input.get("context")
            received_vehicle_id = mission_input.get("vehicle_id")
            received_vehicle_registration_number = mission_input.get(
                "vehicle_registration_number"
            )

            vehicle = (
                find_or_create_vehicle(
                    received_vehicle_id,
                    received_vehicle_registration_number,
                    company,
                )
                if received_vehicle_id or received_vehicle_registration_number
                else None
            )

            mission = Mission(
                name=mission_input.get("name"),
                company=company,
                reception_time=datetime.now(),
                context=context,
                submitter=current_user,
                vehicle=vehicle,
            )
            db.session.add(mission)

        return mission


class EndMission(AuthenticatedMutation):
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
        user_id = graphene.Int(
            required=False,
            description="Optionnel, identifiant du travailleur mobile concerné par la fin de la mission. Par défaut c'est l'auteur de l'opération.",
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(active)
    def mutate(cls, _, info, **args):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            mission = Mission.query.options(
                selectinload(Mission.activities)
            ).get(args.get("mission_id"))

            user_id = args.get("user_id")
            if user_id:
                user = User.query.get(user_id)
            else:
                user = current_user

            if not mission:
                raise AuthorizationError(
                    "Actor is not authorized to log on this mission at this time."
                )

            if not user:
                raise AuthorizationError(
                    f"Actor is not authorized to log for this user."
                )

            existing_mission_end = MissionEnd.query.filter(
                MissionEnd.user_id == user.id,
                MissionEnd.mission_id == mission.id,
            ).one_or_none()

            if existing_mission_end:
                raise MissionAlreadyEndedError(
                    mission_end=existing_mission_end
                )

            user_activities = mission.activities_for(user)
            last_activity = user_activities[-1] if user_activities else None

            end_time = args["end_time"]
            if last_activity:
                if last_activity.start_time > end_time or (
                    last_activity.end_time
                    and last_activity.end_time > end_time
                ):
                    raise UnavailableSwitchModeError(
                        "Invalid time for mission end because there are activities starting or ending after"
                    )
                if not last_activity.end_time:
                    last_activity.revise(
                        reception_time,
                        end_time=args["end_time"],
                    )

            db.session.add(
                MissionEnd(
                    submitter=current_user,
                    reception_time=reception_time,
                    user=user,
                    mission=mission,
                )
            )

        return mission


class ValidateMission(AuthenticatedMutation):
    """
    Validation du contenu (activités + frais) de la mission.

    Retourne la mission.
    """

    class Arguments:
        mission_id = graphene.Int(
            required=True, description="Identifiant de la mission à valider"
        )
        user_id = graphene.Int(
            required=False,
            description="Optionnel, dans le cas d'une validation gestionnaire il est possible de restreindre les informations validées à un travailleur spécifique.",
        )

    Output = MissionValidationOutput

    @classmethod
    @with_authorization_policy(
        check_actor_can_write_on_mission,
        get_target_from_args=lambda *args, **kwargs: Mission.query.options(
            selectinload(Mission.activities).selectinload(Activity.versions)
        ).get(kwargs["mission_id"]),
        error_message="Actor is not authorized to validate the mission",
    )
    def mutate(cls, _, info, mission_id, user_id=None):
        with atomic_transaction(commit_at_end=True):
            mission = Mission.query.get(mission_id)

            user = None
            if user_id:
                user = User.query.get(user_id)
                if not user:
                    raise AuthorizationError(
                        "Actor is not authorized to validate the mission for the user"
                    )

            mission_validation = validate_mission(
                submitter=current_user, mission=mission, for_user=user
            )

        try:
            if mission_validation.is_admin:
                if user:
                    concerned_users = [user]
                else:
                    concerned_users = set([a.user for a in mission.activities])
                for u in concerned_users:
                    warn_if_mission_changes_since_latest_user_action(
                        mission, u
                    )
        except Exception as e:
            app.logger.exception(e)

        return mission_validation


class UpdateMissionVehicle(AuthenticatedMutation):
    class Arguments:
        mission_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de la mission",
        )
        vehicle_id = graphene.Argument(
            graphene.Int,
            required=False,
            description="Identifiant du véhicule utilisé",
        )
        vehicle_registration_number = graphene.Argument(
            graphene.String,
            required=False,
            description="Numéro d'immatriculation du véhicule utilisé, s'il n'est pas déjà enregistré. Un nouveau véhicule sera ajouté.",
        )

    Output = VehicleOutput

    @classmethod
    @with_authorization_policy(
        check_actor_can_write_on_mission,
        get_target_from_args=lambda *args, **kwargs: Mission.query.options(
            selectinload(Mission.activities)
        ).get(kwargs["mission_id"]),
        error_message="Actor is not authorized to set the vehicle for the mission",
    )
    def mutate(
        cls,
        _,
        info,
        mission_id,
        vehicle_id=None,
        vehicle_registration_number=None,
    ):
        with atomic_transaction(commit_at_end=True):
            mission = Mission.query.get(mission_id)
            if not vehicle_id and not vehicle_registration_number:
                app.logger.warning("No vehicle was associated to the mission")
            else:
                vehicle = find_or_create_vehicle(
                    vehicle_id, vehicle_registration_number, mission.company
                )
                mission.vehicle_id = vehicle.id

        return mission.vehicle


class Query(graphene.ObjectType):
    mission = graphene.Field(
        MissionOutput,
        id=graphene.Int(required=True),
        description="Consultation des informations d'une mission",
    )

    @with_authorization_policy(
        can_actor_read_mission,
        get_target_from_args=lambda self, info, id: Mission.query.get(id),
        error_message="Forbidden access",
    )
    def resolve_mission(self, info, id):
        mission = Mission.query.get(id)
        return mission
