import graphene
from graphene.types.generic import GenericScalar
from datetime import datetime
from sqlalchemy.orm import selectinload

from app import app, db
from app.controllers.utils import atomic_transaction
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated_and_active,
)
from app.helpers.graphene_types import TimeStamp
from app.models.mission import Mission
from app.models import Company, Vehicle, User, Comment
from app.models.mission_end import MissionEnd
from app.models.mission_validation import (
    MissionValidation,
    MissionValidationOutput,
)
from app.data_access.mission import MissionOutput
from app.domain.permissions import (
    can_user_log_on_mission_at,
    belongs_to_company_at,
    can_user_access_mission,
)
from app.helpers.authentication import current_user
from app.helpers.errors import (
    AuthorizationError,
    MissionAlreadyEndedError,
    UnavailableSwitchModeError,
    NoActivitiesToValidateError,
    MissionStillRunningError,
)


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
    @with_authorization_policy(authenticated_and_active)
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
                        "Actor is not authorized to create a mission for the company"
                    )

            else:
                company = current_user.primary_company

            if not company:
                raise AuthorizationError("Actor has no primary company")

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
        user_id = graphene.Int(
            required=False,
            description="Optionnel, identifiant du travailleur mobile concerné par la fin de la mission. Par défaut c'est l'auteur de l'opération.",
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(authenticated_and_active)
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

            app.logger.info(f"Ending mission {mission}")
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
                        reception_time, end_time=args["end_time"],
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


class ValidateMission(graphene.Mutation):
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
        can_user_log_on_mission_at,
        get_target_from_args=lambda *args, **kwargs: Mission.query.options(
            selectinload(Mission.activities)
        ).get(kwargs["mission_id"]),
        error_message="Actor is not authorized to validate the mission",
    )
    def mutate(cls, _, info, mission_id, user_id=None):
        with atomic_transaction(commit_at_end=True):
            mission = Mission.query.get(mission_id)

            is_admin_validation = (
                mission.company_id
                in current_user.current_company_ids_with_admin_rights
            )
            user = None
            if user_id:
                if not is_admin_validation and user_id != current_user.id:
                    raise AuthorizationError(
                        "Actor is not authorized to validate the mission for the user"
                    )
                user = User.query.get(user_id)

            if user:
                activities_to_validate = mission.activities_for(user)
            else:
                activities_to_validate = mission.acknowledged_activities

            if not activities_to_validate:
                raise NoActivitiesToValidateError(
                    "There are no activities in the validation scope."
                )

            if any([not a.end_time for a in activities_to_validate]):
                raise MissionStillRunningError()

            mission_validation = MissionValidation(
                submitter=current_user,
                reception_time=datetime.now(),
                mission=mission,
                user=user if is_admin_validation else current_user,
                is_admin=is_admin_validation,
            )
            db.session.add(mission_validation)

        return mission_validation


class Query(graphene.ObjectType):
    mission = graphene.Field(
        MissionOutput,
        id=graphene.Int(required=True),
        description="Consultation des informations d'une mission",
    )

    @with_authorization_policy(
        can_user_log_on_mission_at,
        get_target_from_args=lambda self, info, id: Mission.query.get(id),
        error_message="Forbidden access",
    )
    def resolve_mission(self, info, id):
        mission = Mission.query.get(id)
        app.logger.info(f"Sending mission data for {mission}")
        return mission


class PrivateQuery(graphene.ObjectType):
    is_mission_ended_for_self = graphene.Field(
        graphene.Boolean, mission_id=graphene.Int(required=True)
    )

    @with_authorization_policy(
        can_user_access_mission,
        get_target_from_args=lambda self, info, mission_id: Mission.query.get(
            mission_id
        ),
        error_message="Forbidden access",
    )
    def resolve_is_mission_ended_for_self(self, info, mission_id):
        return (
            MissionEnd.query.filter(
                MissionEnd.user_id == current_user.id,
                MissionEnd.mission_id == mission_id,
            ).count()
            > 0
        )
