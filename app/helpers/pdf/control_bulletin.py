from app.domain.business import get_businesses_display_name
from app.domain.regulations import get_default_business
from app.helpers.pdf import generate_pdf_from_template
from app.models.controller_control import ControlType


def generate_control_bulletin_pdf(control):

    #Déterminer le(s) type(s) d'activités à afficher dans le BDC
    is_control_mobilic = control.control_type == ControlType.mobilic
    if is_control_mobilic:
        business_ids = list(
            control.control_bulletin.get("employments_business_types").values()
        )
        business_types = get_businesses_display_name(business_ids=business_ids)
    else:
        business_id = control.control_bulletin.get("business_id", None)
        business = get_default_business(business_id=business_id)
        business_types = business.display_name

    #Signature de l'agent
    #CTT=greco id
    #IT=nom de l'agent
    controller = control.controller_user
    controller_signature = controller.greco_id if controller._is_ctt() else f"{controller.last_name} {controller.first_name}"

    return generate_pdf_from_template(
        "control_bulletin.html",
        control_bulletin_id=control.reference,
        control_time=control.creation_time,
        control_end_time=control.control_bulletin_update_time,
        control_date=control.creation_time,
        control_location=f"{control.control_bulletin.get('location_lieu')}, {control.control_bulletin.get('location_commune')}",
        controlled_employee_first_name=control.user_first_name,
        controlled_employee_last_name=control.user_last_name,
        controlled_employee_birth_date=control.control_bulletin.get('user_birth_date'),
        controlled_employee_nationality=control.control_bulletin.get('user_nationality'),
        controlled_company_siren=control.control_bulletin.get('siren'),
        controlled_company_name=control.company_name,
        controlled_company_address=f"{control.control_bulletin.get('company_address')}",
        transport_type=control.control_bulletin.get("transport_type"),
        articles_nature=control.control_bulletin.get("articles_nature"),
        license_number=control.control_bulletin.get("license_number"),
        license_copy_number=control.control_bulletin.get(
            "license_copy_number"
        ),
        vehicle_registration_number=control.vehicle_registration_number,
        vehicle_registration_country=control.control_bulletin.get(
            "vehicle_registration_country"
        ),
        is_vehicle_immobilized=control.control_bulletin.get(
            "is_vehicle_immobilized"
        ),
        transport_from=control.control_bulletin.get("mission_address_begin"),
        transport_to=control.control_bulletin.get("mission_address_end"),
        observations=control.control_bulletin.get("observation"),
        business_types=business_types,
        controller_signature=controller_signature
    )
