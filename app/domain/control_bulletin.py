import json
import re

from app.helpers.errors import InvalidParamsError
from app.models.business import Business, BusinessType


def save_control_bulletin(
    control,
    user_first_name=None,
    user_last_name=None,
    user_nationality=None,
    user_birth_date=None,
    siren=None,
    company_name=None,
    company_address=None,
    location_commune=None,
    location_department=None,
    location_lieu=None,
    location_id=None,
    vehicle_registration_number=None,
    vehicle_registration_country=None,
    mission_address_begin=None,
    mission_address_end=None,
    transport_type=None,
    articles_nature=None,
    license_number=None,
    license_copy_number=None,
    observation=None,
    is_vehicle_immobilized=False,
    business_id=None,
    is_day_page_filled=None,
    delivered_by_hand=None,
    vehicle_weight=None,
    real_vehicle_weight=None,
):
    if control.control_bulletin:
        existing_bulletin = control.control_bulletin
    else:
        existing_bulletin = {}

    control.user_first_name = user_first_name
    control.user_last_name = user_last_name
    control.vehicle_registration_number = vehicle_registration_number
    control.company_name = company_name
    control.is_day_page_filled = is_day_page_filled
    control.delivered_by_hand = delivered_by_hand
    existing_bulletin["user_birth_date"] = (
        user_birth_date.isoformat() if user_birth_date else None
    )
    existing_bulletin["user_nationality"] = user_nationality
    existing_bulletin["siren"] = siren
    existing_bulletin["company_address"] = company_address
    existing_bulletin["location_commune"] = location_commune
    existing_bulletin["location_department"] = location_department
    existing_bulletin["location_lieu"] = location_lieu
    existing_bulletin["location_id"] = location_id
    existing_bulletin["vehicle_registration_country"] = (
        vehicle_registration_country
    )
    existing_bulletin["mission_address_begin"] = mission_address_begin
    existing_bulletin["mission_address_end"] = mission_address_end
    existing_bulletin["transport_type"] = transport_type
    existing_bulletin["articles_nature"] = articles_nature
    existing_bulletin["license_number"] = license_number
    existing_bulletin["license_copy_number"] = license_copy_number
    existing_bulletin["observation"] = observation
    existing_bulletin["is_vehicle_immobilized"] = is_vehicle_immobilized
    existing_bulletin["business_id"] = business_id
    existing_bulletin["vehicle_weight"] = vehicle_weight
    existing_bulletin["real_vehicle_weight"] = real_vehicle_weight

    control.control_bulletin = existing_bulletin


def get_location_info_from_bulletin(bulletin):
    """Returns (department_code, department_label, postal_code)."""
    if not bulletin:
        return "", "", ""

    location_department = bulletin.get("location_department", "")
    location_commune = bulletin.get("location_commune", "")
    location_lieu = bulletin.get("location_lieu", "")

    # Extract postal code from commune or lieu
    postal_code = ""
    if (
        location_commune
        and "(" in location_commune
        and ")" in location_commune
    ):
        potential_postal = (
            location_commune.split("(")[-1].split(")")[0].strip()
        )
        if potential_postal.isdigit() and len(potential_postal) == 5:
            postal_code = potential_postal

    if not postal_code and location_lieu:
        postal_match = re.search(r"\b(\d{5})\b", location_lieu)
        if postal_match:
            postal_code = postal_match.group(1)

    # Parse department info
    department_code = ""
    department_label = ""

    if location_department:
        try:
            dept_obj = json.loads(location_department)
            if isinstance(dept_obj, dict) and "code" in dept_obj:
                department_code = dept_obj["code"]
                department_label = dept_obj.get("label", "")
            else:
                department_label = location_department
        except (json.JSONDecodeError, TypeError):
            department_label = location_department

    # Fallback to postal code if needed. DROM-COM postal codes (971xx-976xx)
    # need the 3-digit department code to be distinguishable from one
    # another, everywhere else uses the 2-digit code.
    if not department_code and postal_code:
        department_code = (
            postal_code[:3]
            if postal_code.startswith("97")
            else postal_code[:2]
        )

    return department_code, department_label, postal_code
