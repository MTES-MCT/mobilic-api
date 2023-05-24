from app.helpers.pdf import generate_pdf_from_template


def generate_control_bulletin_pdf(control_bulletin):
    return generate_pdf_from_template(
        "control_bulletin.html",
        control_bulletin_id="0167-2022-IDCONTROLEUR",
        control_time=control_bulletin.creation_time.strftime("%H:%M"),
        control_date=control_bulletin.creation_time.strftime("%d/%m/%Y"),
        control_location="Département, commune, lieu",
        controlled_employee=f"{control_bulletin.user_last_name} {control_bulletin.user_first_name}",
        controlled_company=control_bulletin.siren,
        transport_type=control_bulletin.transport_type,
        articles_nature=control_bulletin.articles_nature,
        license_number=control_bulletin.license_number,
        license_copy_number=control_bulletin.license_copy_number,
        vehicle_registration_number=control_bulletin.vehicle_registration_number,
        vehicle_registration_country=control_bulletin.vehicle_registration_country,
        transport_from=control_bulletin.mission_address_begin,
        transport_to=control_bulletin.mission_address_end,
        observations=control_bulletin.observation,
        controller_name="",
    )
