"""Shared utilities for Brevo data processing."""

from typing import List, Dict, Any
from sqlalchemy import func
from app import db
from app.models import Company, Employment, User
from app.models.user import UserAccountStatus


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


def get_creator_activation_status(
    company_ids: List[int],
) -> Dict[int, bool]:
    """Check if company creators have activated their accounts.

    IMPORTANT: This function checks ONLY the company creator's account status.
    The creator is the first admin (earliest employment ID) who registered the company.
    A company is considered "activated" when its creator has activated their account.

    This is used to determine if a company should be in Acquisition or Activation funnel:
    - No creator activation → Acquisition funnel
    - Creator activated → Activation funnel (if other criteria met)

    Args:
        company_ids: List of company IDs to check

    Returns:
        Dictionary mapping company_id to activation status (True/False)
        - True: Creator account is active
        - False: Creator account is not active or not found
    """
    if not company_ids:
        return {}

    first_admins = (
        db.session.query(
            Employment.company_id,
            func.min(Employment.id).label("creator_id"),
        )
        .filter(
            Employment.company_id.in_(company_ids),
            Employment.has_admin_rights == True,
        )
        .group_by(Employment.company_id)
        .subquery()
    )

    stats = (
        db.session.query(
            Employment.company_id,
            func.count(User.id).label("active_count"),
        )
        .join(User, Employment.user_id == User.id)
        .join(
            first_admins,
            (Employment.company_id == first_admins.c.company_id)
            & (Employment.id == first_admins.c.creator_id),
        )
        .filter(
            Employment.company_id.in_(company_ids),
            Employment.has_admin_rights == True,
            User.status == UserAccountStatus.ACTIVE,
        )
        .group_by(Employment.company_id)
        .all()
    )

    return {stat.company_id: stat.active_count > 0 for stat in stats}
