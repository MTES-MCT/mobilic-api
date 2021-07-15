import requests

from app import app
from app.helpers.insee_tranche_effectifs import format_tranche_effectif
from app.models import NafCode


def call_integromat_webhook(company, admin=None):
    siren_api_info = company.siren_api_info

    if not admin:
        sorted_employments = sorted(
            company.employments, key=lambda e: e.creation_time
        )
        if not sorted_employments:
            raise ValueError("There is no employment in the company")
        admin = sorted_employments[0].user

    first_establishment_info = (
        siren_api_info["etablissements"][0] if siren_api_info else None
    )
    formatted_main_activity = None
    if siren_api_info:
        main_activity_code = siren_api_info["uniteLegale"][
            "activitePrincipaleUniteLegale"
        ]
        main_activity = (
            NafCode.get_code(main_activity_code)
            if main_activity_code
            else None
        )
        if main_activity:
            formatted_main_activity = (
                f"{main_activity.code} {main_activity.label}"
            )

    response = requests.post(
        app.config["INTEGROMAT_COMPANY_SIGNUP_WEBHOOK"],
        data=dict(
            name=company.name,
            creation_time=company.creation_time,
            submitter_name=admin.display_name,
            submitter_email=admin.email,
            siren=company.siren,
            metabase_link=f"{app.config['METABASE_COMPANY_DASHBOARD_BASE_URL']}{company.id}",
            location=f"{first_establishment_info.get('adresse', '')} {first_establishment_info.get('codePostal', '')}"
            if first_establishment_info
            else None,
            activity_code=formatted_main_activity or "inconnu",
            n_employees=format_tranche_effectif(
                siren_api_info["uniteLegale"]["trancheEffectifsUniteLegale"]
                if siren_api_info
                else ""
            ),
            n_employees_year=siren_api_info["uniteLegale"][
                "anneeEffectifsUniteLegale"
            ]
            if siren_api_info
            else "",
        ),
        timeout=3,
    )
    if not response.status_code == 200:
        app.logger.warning(
            f"Creation of Trello card for {company} failed with error : {response.text}"
        )
