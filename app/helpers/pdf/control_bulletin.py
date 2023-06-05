import json

from app.helpers.pdf import generate_pdf_from_template


def generate_control_bulletin_pdf(control, controller_user):
    control_bulletin = json.loads(control.control_bulletin)

    return generate_pdf_from_template(
        "control_bulletin.html",
        control_bulletin_id=control.reference,
        organizational_unit=controller_user.organizational_unit,
        control_time=control.creation_time,
        control_date=control.creation_time,
        control_location="Département, commune, lieu",
        controlled_employee=f"{control.user_last_name} {control.user_first_name}",
        controlled_company=control_bulletin.get("siren"),
        transport_type=control_bulletin.get("transport_type"),
        articles_nature=control_bulletin.get("articles_nature"),
        license_number=control_bulletin.get("license_number"),
        license_copy_number=control_bulletin.get("license_copy_number"),
        vehicle_registration_number=control.vehicle_registration_number,
        vehicle_registration_country=control_bulletin.get(
            "vehicle_registration_country"
        ),
        transport_from=control_bulletin.get("mission_address_begin"),
        transport_to=control_bulletin.get("mission_address_end"),
        observations=control_bulletin.get("observation"),
        controller_name=f"{controller_user.last_name} {controller_user.first_name}",
    )
