from datetime import datetime

import graphene

from app import db
from app.controllers.utils import Void, atomic_transaction
from app.domain.permissions import company_admin
from app.domain.team import remove_vehicle_from_all_teams
from app.helpers.authentication import current_user, AuthenticatedMutation
from app.helpers.authorization import with_authorization_policy
from app.models.vehicle import VehicleOutput, Vehicle


class CreateVehicle(AuthenticatedMutation):
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
        company_admin,
        get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
    )
    def mutate(cls, _, info, registration_number, company_id, alias=None):
        with atomic_transaction(commit_at_end=True):

            vehicle = Vehicle.query.filter(
                Vehicle.company_id == company_id,
                Vehicle.registration_number == registration_number,
                Vehicle.terminated_at is not None,
            ).one_or_none()

            if not vehicle:
                vehicle = Vehicle(
                    registration_number=registration_number,
                    alias=alias,
                    submitter=current_user,
                    company_id=company_id,
                )
                db.session.add(vehicle)
            else:
                vehicle.terminated_at = None
                vehicle.alias = alias
        return vehicle


class EditVehicle(AuthenticatedMutation):
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
        company_admin,
        get_target_from_args=lambda *args, **kwargs: Vehicle.query.get(
            kwargs["id"]
        ).company_id,
    )
    def mutate(cls, _, info, id, alias=None):
        vehicle = Vehicle.query.get(id)
        vehicle.alias = alias
        db.session.commit()
        return vehicle


class TerminateVehicle(AuthenticatedMutation):
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
        company_admin,
        get_target_from_args=lambda *args, **kwargs: Vehicle.query.get(
            kwargs["id"]
        ).company_id,
    )
    def mutate(cls, _, info, id):
        vehicle = Vehicle.query.get(id)
        vehicle.terminated_at = datetime.now()

        try:
            remove_vehicle_from_all_teams(vehicle)
        except Exception:
            pass

        db.session.commit()
        return Void(success=True)
