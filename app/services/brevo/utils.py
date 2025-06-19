"""Shared utilities for Brevo data processing."""

from typing import List, Dict, Any
from app import db
from app.models import Company, Employment, User


def extract_siren(siren_api_info):
    """Extract SIREN from SIREN API info."""
    if not siren_api_info or not siren_api_info.get("uniteLegale"):
        return None
    return siren_api_info["uniteLegale"].get("siren")


def extract_siret(siren_api_info):
    """Extract SIRET from SIREN API info."""
    if not siren_api_info or not siren_api_info.get("etablissements"):
        return None
    etablissements = siren_api_info["etablissements"]
    if not etablissements:
        return None

    for etablissement in etablissements:
        if etablissement.get("etablissementSiege"):
            return etablissement.get("siret")

    return etablissements[0].get("siret")


def get_companies_base_data() -> List[Dict[str, Any]]:
    """Get base company data shared by both acquisition and activation finders."""
    companies = (
        db.session.query(
            Company.id,
            Company.usual_name,
            Company.siren_api_info,
            Company.phone_number,
            Company.number_workers,
            Company.creation_time,
        )
        .filter(Company.has_ceased_activity == False)
        .order_by(Company.creation_time.desc())
        .all()
    )

    return [
        {
            "id": c.id,
            "name": c.usual_name,
            "siren": extract_siren(c.siren_api_info),
            "siret": extract_siret(c.siren_api_info),
            "phone_number": c.phone_number,
            "nb_employees": c.number_workers,
            "creation_date": c.creation_time.date(),
        }
        for c in companies
    ]


def get_admin_info(company_ids: List[int]) -> Dict[int, Dict[str, str]]:
    """Get admin information for companies."""
    if not company_ids:
        return {}

    admins = (
        db.session.query(
            Employment.company_id,
            User.email,
            User.first_name,
            User.last_name,
        )
        .join(User, Employment.user_id == User.id)
        .filter(
            Employment.company_id.in_(company_ids),
            Employment.has_admin_rights == True,
            Employment.validation_status == "approved",
            Employment.dismissed_at.is_(None),
        )
        .distinct(Employment.company_id)
        .all()
    )

    return {
        admin.company_id: {
            "email": admin.email,
            "first_name": admin.first_name,
            "last_name": admin.last_name,
        }
        for admin in admins
    }
