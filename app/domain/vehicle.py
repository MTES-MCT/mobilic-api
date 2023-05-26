from sqlalchemy import func

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
        vehicles = find_vehicle(
            registration_number=vehicle_registration_number,
            company_id=company_id,
        )
        vehicle = vehicles[0] if vehicles else None
        vehicle_registration_number = vehicle_registration_number.upper()

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
            vehicle.registration_number = vehicle_registration_number
            if alias:
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


def find_vehicle(registration_number, company_id):
    vehicle_registration_number = registration_number.upper()
    return Vehicle.query.filter(
        func.translate(Vehicle.registration_number, "- ", "").ilike(
            func.translate(vehicle_registration_number, "- ", "")
        ),
        Vehicle.company_id == company_id,
    ).all()
