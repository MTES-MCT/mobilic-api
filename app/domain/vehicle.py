import re

from sqlalchemy import func

from app import db
from app.helpers.authentication import current_user
from app.models import Vehicle


def normalize_registration_number(registration_number):
    """
    Clean and normalize vehicle registration numbers for consistent matching.
    """
    if not registration_number:
        return None

    # Input validation
    if not isinstance(registration_number, str):
        raise ValueError("registration_number must be a string")

    # Prevent excessively long inputs
    if len(registration_number) > 50:
        raise ValueError("registration_number too long (max 50 characters)")

    # Allow only safe characters to prevent injection
    allowed_pattern = r"^[a-zA-Z0-9\s\-\(\)\.\_]+$"
    if not re.match(allowed_pattern, registration_number):
        raise ValueError("registration_number contains invalid characters")

    # Convert to uppercase
    upper_reg = registration_number.upper().strip()

    # Handle special case: numbers in parentheses containing FR
    clean_parentheses_pattern = r"^[0-9\s]{0,10}\(([a-zA-Z0-9\-\s]{2,15}FR[a-zA-Z0-9\-\s]{2,15})\)\s{0,5}$"

    try:
        match = re.match(clean_parentheses_pattern, upper_reg, re.IGNORECASE)

        if match:
            # Extract content from parentheses and normalize
            extracted = match.group(1)
            # Verify it's a valid French registration format
            normalized_extracted = re.sub(r"[^A-Z0-9]", "", extracted)

            # French registration pattern validation
            if re.match(
                r"^[A-Z]{2,3}[0-9]{3}[A-Z]{1,2}$", normalized_extracted
            ):
                return normalized_extracted
    except re.error:
        # Fallback if regex fails
        pass

    # Standard normalization
    normalized = re.sub(r"[^A-Z0-9]", "", upper_reg)

    # Final length check
    if len(normalized) > 20:
        raise ValueError("Normalized registration_number too long")

    return normalized


def find_existing_vehicle_by_normalized_registration(
    company_id, registration_number
):
    """
    Find existing vehicles using exact match first, then normalized search.
    Also handles reactivation of terminated vehicles when appropriate.
    """
    if not registration_number:
        return None

    # Basic input validation
    if not isinstance(company_id, int) or company_id <= 0:
        raise ValueError("Invalid company_id")

    if (
        not isinstance(registration_number, str)
        or len(registration_number.strip()) == 0
    ):
        return None

    # Clean input for safety
    safe_registration = registration_number.strip()[:50]

    # Step 1: Try exact match first (active vehicles only)
    exact_vehicle = (
        Vehicle.query.filter(
            Vehicle.company_id == company_id,
            Vehicle.registration_number == safe_registration,
            Vehicle.terminated_at.is_(None),
        )
        .order_by(Vehicle.creation_time.desc())
        .first()
    )

    if exact_vehicle:
        return exact_vehicle

    # Step 2: Try normalized search on active vehicles
    try:
        normalized_registration = normalize_registration_number(
            safe_registration
        )
    except ValueError:
        # If normalization fails, just return None
        return None

    if not normalized_registration:
        return None

    # Search among active vehicles with normalized comparison
    active_vehicles = (
        Vehicle.query.filter(
            Vehicle.company_id == company_id, Vehicle.terminated_at.is_(None)
        )
        .order_by(Vehicle.creation_time.desc())
        .all()
    )

    for vehicle in active_vehicles:
        try:
            if (
                normalize_registration_number(vehicle.registration_number)
                == normalized_registration
            ):
                return vehicle
        except (ValueError, TypeError):
            continue  # Skip vehicles with problematic registration numbers

    # Step 3: Check for exact match among terminated vehicles
    exact_terminated_vehicle = (
        Vehicle.query.filter(
            Vehicle.company_id == company_id,
            Vehicle.registration_number == safe_registration,
            Vehicle.terminated_at.is_not(None),
        )
        .order_by(Vehicle.creation_time.desc())
        .first()
    )

    if exact_terminated_vehicle:
        # Reactivate the exactly matching terminated vehicle
        exact_terminated_vehicle.terminated_at = None
        db.session.flush()
        return exact_terminated_vehicle

    # Step 4: Check normalized match among all vehicles (including terminated)
    all_vehicles = (
        Vehicle.query.filter(Vehicle.company_id == company_id)
        .order_by(Vehicle.creation_time.desc())
        .all()
    )

    for vehicle in all_vehicles:
        try:
            if (
                normalize_registration_number(vehicle.registration_number)
                == normalized_registration
            ):
                if vehicle.terminated_at:
                    vehicle.terminated_at = None
                    db.session.flush()
                return vehicle
        except (ValueError, TypeError):
            continue

    return None


def find_or_create_vehicle(
    company_id, vehicle_registration_number, alias=None, submitter=None
):
    vehicle = None
    if vehicle_registration_number:
        # Use the normalized search function
        vehicle = find_existing_vehicle_by_normalized_registration(
            company_id, vehicle_registration_number
        )

        # Create new vehicle if none found
        if not vehicle:
            if submitter:
                vehicle = Vehicle(
                    registration_number=vehicle_registration_number.upper(),
                    alias=alias,
                    company_id=company_id,
                    submitter=submitter,
                )
            else:
                vehicle = Vehicle(
                    registration_number=vehicle_registration_number.upper(),
                    alias=alias,
                    company_id=company_id,
                )
            db.session.add(vehicle)

    return vehicle


def find_vehicle(registration_number, company_id):
    vehicle_registration_number = registration_number.upper()
    return Vehicle.query.filter(
        func.translate(Vehicle.registration_number, "- ", "").ilike(
            func.translate(vehicle_registration_number, "- ", "")
        ),
        Vehicle.company_id == company_id,
    ).all()
