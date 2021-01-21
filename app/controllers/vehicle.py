import graphene
from datetime import datetime

from app.controllers.utils import Void
from app.helpers.authentication import current_user

from app.domain.permissions import company_admin_at
from app.helpers.authorization import with_authorization_policy
from app import db, app
from app.models.vehicle import VehicleOutput, Vehicle


class CreateVehicle(graphene.Mutation):
    """
    Ajout d'un nouveau véhicule à la liste.

    Renvoie le véhicule nouvellement ajouté.
    """

    class Arguments:
        registration_number = graphene.String(
            required=True, description="Numéro d'immatriculation du véhicule"
        )
        alias = graphene.String(
            required=False, description="Nom usuel optionnel du véhicule"
        )
        company_id = graphene.Int(
            required=True,
            description="Identifiant de l'entreprise du véhicule",
        )

    Output = VehicleOutput

    @classmethod
    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
    )
    def mutate(cls, _, info, registration_number, company_id, alias=None):
        vehicle = Vehicle(
            registration_number=registration_number,
            alias=alias,
            submitter=current_user,
            company_id=company_id,
        )
        try:
            db.session.add(vehicle)
            db.session.commit()
            app.logger.info(f"Created new vehicle {vehicle}")
        except Exception as e:
            app.logger.exception(f"Error vehicle creation for {vehicle}")
        return vehicle


class EditVehicle(graphene.Mutation):
    """
    Edition du nom usuel d'un véhicule.

    Renvoie le véhicule édité.
    """

    class Arguments:
        alias = graphene.String(
            required=False, description="Nouveau nom usuel"
        )
        id = graphene.Int(
            required=True, description="Identifiant du véhicule à éditer"
        )

    Output = VehicleOutput

    @classmethod
    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda *args, **kwargs: Vehicle.query.get(
            kwargs["id"]
        ).company_id,
    )
    def mutate(cls, _, info, alias, id):
        vehicle = Vehicle.query.get(id)
        vehicle.alias = alias
        db.session.commit()
        app.logger.info(f"Updated vehicle {vehicle}")
        return vehicle


class TerminateVehicle(graphene.Mutation):
    """
    Retrait d'un véhicule de la liste.
    """

    class Arguments:
        id = graphene.Int(
            required=True, description="Identifiant du véhicule à retirer"
        )

    Output = Void

    @classmethod
    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda *args, **kwargs: Vehicle.query.get(
            kwargs["id"]
        ).company_id,
    )
    def mutate(cls, _, info, id):
        vehicle = Vehicle.query.get(id)
        vehicle.terminated_at = datetime.now()
        db.session.commit()
        app.logger.info(f"Updated vehicle {vehicle}")
        return Void(success=True)
