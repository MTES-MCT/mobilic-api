from app.helpers.pdf import generate_pdf_from_template
from app.models.controller_control import ControlType


def generate_control_bulletin_pdf(control, controller_user):

    return generate_pdf_from_template(
        "control_bulletin.html",
        control_bulletin_id=control.reference,
        organizational_unit=controller_user.pretty_organizational_unit,
        control_time=control.creation_time,
        control_date=control.creation_time,
        control_location=f"{control.control_bulletin.get('location_lieu')}, {control.control_bulletin.get('location_commune')}",
        controlled_employee=f"{control.user_last_name} {control.user_first_name}",
        controlled_company=f"{control.company_name} - {control.control_bulletin.get('siren')}",
        controller_company_address=f"{control.control_bulletin.get('company_address')}",
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
        controller_name=f"{controller_user.last_name} {controller_user.first_name}",
        infraction_labels=control.reported_infractions_labels,
        history_start_date=control.history_start_date,
        history_end_date=control.history_end_date,
    )
