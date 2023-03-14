import graphene
from graphene.types.generic import GenericScalar
from datetime import datetime
from sqlalchemy.orm import selectinload

from app import app, db
from app.controllers.activity import BulkActivityItem, play_bulk_activity_items
from app.controllers.expenditure import (
    BulkExpenditureItem,
    cancel_expenditure,
    log_expenditure_,
)
from app.controllers.utils import atomic_transaction
from app.domain.notifications import (
    warn_if_mission_changes_since_latest_user_action,
)
from app.domain.validation import validate_mission
from app.helpers.authorization import (
    with_authorization_policy,
    active,
    check_company_against_scope_wrapper,
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
    get_employment_over_period,
    is_employed_by_company_over_period,
    can_actor_read_mission,
    company_admin,
    check_actor_can_write_on_mission_for_user,
)
from app.helpers.authentication import current_user, AuthenticatedMutation
from app.helpers.errors import (
    AuthorizationError,
    MissionAlreadyEndedError,
    UnavailableSwitchModeError,
)
from app.models.vehicle import VehicleOutput


def find_or_create_vehicle(
    vehicle_id, vehicle_registration_number, company, employment
):
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

        if (
            employment
            and employment.team
            and len(employment.team.vehicles) > 0
            and vehicle not in employment.team.vehicles
        ):
            employment.team.vehicles.append(vehicle)

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
        required=True,
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
    creation_time = graphene.Argument(
        TimeStamp,
        required=False,
        description="Optionnel, date de saisie de début de mission",
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
    @check_company_against_scope_wrapper(
        company_id_resolver=lambda *args, **kwargs: kwargs["company_id"]
    )
    def mutate(cls, _, info, **mission_input):
        with atomic_transaction(commit_at_end=True):
            # Preload resources
            company_id = mission_input["company_id"]
            company = Company.query.get(company_id)
            employment = get_employment_over_period(
                current_user, company, include_pending_invite=False
            )
            if employment is None:
                raise AuthorizationError(
                    "Actor is not authorized to create a mission for the company"
                )

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
                    employment,
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
                creation_time=mission_input.get("creation_time"),
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
        creation_time = graphene.Argument(
            TimeStamp,
            required=False,
            description="Optionnel, date de saisie de fin de mission",
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(active)
    @check_company_against_scope_wrapper(
        company_id_resolver=lambda *args, **kwargs: Mission.query.get(
            kwargs["mission_id"]
        ).company.id
    )
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
                        creation_time=args.get("creation_time"),
                    )

            db.session.add(
                MissionEnd(
                    submitter=current_user,
                    reception_time=reception_time,
                    user=user,
                    mission=mission,
                    creation_time=args.get("creation_time"),
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
        users_ids = graphene.List(
            graphene.Int,
            required=True,
            description="Identifiants des utilisateurs dont on veut valider les saisies.",
        )
        creation_time = graphene.Argument(
            TimeStamp,
            required=False,
            description="Optionnel, date de saisie de la validation",
        )
        activity_items = graphene.List(
            BulkActivityItem,
            required=False,
            description="Optionnel, liste de modifications/créations d'activités à jouer avant validation",
        )
        expenditures_cancel_ids = graphene.List(
            graphene.Int,
            required=False,
            description="Optionnel, identifiants des frais à annuler",
        )
        expenditures_inputs = graphene.List(
            BulkExpenditureItem,
            required=False,
            description="Optionnel, frais à créer",
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(
        check_actor_can_write_on_mission,
        get_target_from_args=lambda *args, **kwargs: Mission.query.options(
            selectinload(Mission.activities).selectinload(Activity.versions)
        ).get(kwargs["mission_id"]),
        error_message="Actor is not authorized to validate the mission",
    )
    def mutate(
        cls,
        _,
        info,
        mission_id,
        users_ids=None,
        creation_time=None,
        activity_items=[],
        expenditures_cancel_ids=[],
        expenditures_inputs=[],
    ):
        with atomic_transaction(commit_at_end=True):
            play_bulk_activity_items(activity_items)

            for expenditure_cancel_id in expenditures_cancel_ids:
                cancel_expenditure(expenditure_cancel_id)

            for expenditure_input in expenditures_inputs:
                log_expenditure_(expenditure_input)

            mission = Mission.query.get(mission_id)

            for user_id in users_ids:
                user = User.query.get(user_id)
                if not user:
                    raise AuthorizationError(
                        "Actor is not authorized to validate the mission for the user"
                    )
                mission_validation = validate_mission(
                    submitter=current_user,
                    mission=mission,
                    creation_time=creation_time,
                    for_user=user,
                )
                try:
                    if mission_validation.is_admin:
                        if user:
                            concerned_users = [user]
                        else:
                            concerned_users = set(
                                [a.user for a in mission.activities]
                            )
                        for u in concerned_users:
                            warn_if_mission_changes_since_latest_user_action(
                                mission, u
                            )
                except Exception as e:
                    app.logger.exception(e)

        return mission


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
                employment = get_employment_over_period(
                    current_user, mission.company, include_pending_invite=False
                )
                vehicle = find_or_create_vehicle(
                    vehicle_id,
                    vehicle_registration_number,
                    mission.company,
                    employment,
                )
                mission.vehicle_id = vehicle.id

        return mission.vehicle


class ChangeMissionName(AuthenticatedMutation):
    class Arguments:
        mission_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de la mission",
        )
        name = graphene.Argument(
            graphene.String,
            required=True,
            description="Nom de la mission",
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(
        check_actor_can_write_on_mission,
        get_target_from_args=lambda *args, **kwargs: Mission.query.options(
            selectinload(Mission.activities)
        ).get(kwargs["mission_id"]),
        error_message="Actor is not authorized to change the name of the mission",
    )
    def mutate(cls, _, info, mission_id, name):
        with atomic_transaction(commit_at_end=True):
            mission = Mission.query.get(mission_id)
            mission.name = name

        return mission


class CancelMission(AuthenticatedMutation):
    class Arguments:
        mission_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de la mission dont les activités sont à annuler",
        )
        user_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de l'utilisateur dont les activités sont à annuler",
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(
        check_actor_can_write_on_mission_for_user,
        get_target_from_args=lambda *args, **kwargs: {
            "mission": Mission.query.options(
                selectinload(Mission.activities)
            ).get(kwargs["mission_id"]),
            "for_user": User.query.get(kwargs["user_id"]),
        },
        error_message="Actor is not authorized to cancel the mission",
    )
    def mutate(cls, _, info, mission_id, user_id):
        with atomic_transaction(commit_at_end=True):
            mission = Mission.query.get(mission_id)
            user = User.query.get(user_id)
            activities_to_update = mission.activities_for(user)
            for activity in activities_to_update:
                activity.dismiss()
        return mission


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
    @check_company_against_scope_wrapper(
        company_id_resolver=lambda self, info, id: Mission.query.get(
            id
        ).company.id
    )
    def resolve_mission(self, info, id):
        mission = Mission.query.get(id)
        return mission
