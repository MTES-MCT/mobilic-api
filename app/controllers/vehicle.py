import graphene
from datetime import datetime
from app.helpers.authentication import current_user

from app.domain.permissions import company_admin
from app.helpers.authorization import with_authorization_policy
from app import db, app
from app.models.vehicle import VehicleOutput, Vehicle


class CreateVehicle(graphene.Mutation):
    class Arguments:
        registration_number = graphene.String(required=True)
        alias = graphene.String(required=False)
        company_id = graphene.Int(required=True)

    vehicle = graphene.Field(VehicleOutput)

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
    )
    def mutate(cls, _, info, registration_number, alias, company_id):
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
        return CreateVehicle(vehicle=vehicle)


class EditVehicle(graphene.Mutation):
    class Arguments:
        alias = graphene.String(required=False)
        id = graphene.Int(required=True)

    vehicle = graphene.Field(VehicleOutput)

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: Vehicle.query.get(
            kwargs["id"]
        ).company_id,
    )
    def mutate(cls, _, info, alias, id):
        vehicle = Vehicle.query.get(id)
        vehicle.alias = alias
        db.session.commit()
        app.logger.info(f"Updated vehicle {vehicle}")
        return EditVehicle(vehicle=vehicle)


class TerminateVehicle(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Field(graphene.Boolean)

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
        db.session.commit()
        app.logger.info(f"Updated vehicle {vehicle}")
        return TerminateVehicle(success=True)
