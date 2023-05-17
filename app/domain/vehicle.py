from app import db
from app.helpers.authentication import current_user
from app.models import Vehicle


def find_or_create_vehicle(
    company_id,
    vehicle_id=None,
    vehicle_registration_number=None,
    alias=None,
    employment=None,
):
    if not vehicle_id:
        vehicle_registration_number = vehicle_registration_number.upper()
        vehicle = Vehicle.query.filter(
            Vehicle.registration_number.ilike(vehicle_registration_number),
            Vehicle.company_id == company_id,
        ).first()

        if not vehicle:
            vehicle = Vehicle(
                registration_number=vehicle_registration_number,
                submitter=current_user,
                alias=alias,
                company_id=company_id,
            )
            db.session.add(vehicle)
            db.session.flush()  # To get a DB id for the new vehicle
        else:
            vehicle.terminated_at = None
            vehicle.alias = alias

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
            Vehicle.company_id == company_id,
        ).one_or_none()

    return vehicle
