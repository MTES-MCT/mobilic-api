import requests

from app import app
from app.helpers.insee_tranche_effectifs import format_tranche_effectif
from app.models import NafCode


def call_integromat_webhook(company, legal_unit, open_facilities, admin=None):
    if not admin:
        sorted_employments = sorted(
            company.employments, key=lambda e: e.creation_time
        )
        if not sorted_employments:
            raise ValueError("There is no employment in the company")
        admin = sorted_employments[0].user

    first_establishment_info = open_facilities[0] if open_facilities else None

    response = requests.post(
        app.config["INTEGROMAT_COMPANY_SIGNUP_WEBHOOK"],
        data=dict(
            name=company.name,
            creation_time=company.creation_time,
            submitter_name=admin.display_name,
            submitter_email=admin.email,
            siren=company.siren,
            metabase_link=f"{app.config['METABASE_COMPANY_DASHBOARD_BASE_URL']}{company.id}",
            location=f"{first_establishment_info.address} {first_establishment_info.postal_code}"
            if first_establishment_info
            else None,
            activity_code=legal_unit.activity if legal_unit else "inconnu",
            n_employees=legal_unit.tranche_effectif if legal_unit else "",
            n_employees_year=legal_unit.tranche_effectif_year
            if legal_unit
            else "",
        ),
        timeout=3,
    )
    if not response.status_code == 200:
        app.logger.warning(
            f"Creation of Trello card for {company} failed with error : {response.text}"
        )
