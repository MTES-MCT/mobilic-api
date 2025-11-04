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

    control.control_bulletin = existing_bulletin
