"""Acquisition funnel data finder."""

from datetime import date
from sqlalchemy import func
from typing import List, Dict, Any

from app import db
from app.models import Company, Employment, User
from ._config import BrevoFunnelConfig


class AcquisitionDataFinder:
    """Data finder for acquisition funnel companies."""

    def __init__(self):
        self.config = BrevoFunnelConfig()

    def find_companies(
        self, exclude_company_ids: List[int] = None
    ) -> List[Dict[str, Any]]:
        """Find companies for acquisition funnel.

        Args:
            exclude_company_ids: Company IDs to exclude (e.g., already in activation)

        Returns:
            List of company dictionaries with acquisition data
        """
        companies_base = self._get_companies_base_data()
        if not companies_base:
            return []

        if exclude_company_ids:
            companies_base = [
                c for c in companies_base if c["id"] not in exclude_company_ids
            ]

        company_ids = [c["id"] for c in companies_base]
        invitation_stats = self._get_invitation_stats(company_ids)
        admin_info = self._get_admin_info(company_ids)

        acquisition_companies = []
        for company in companies_base:
            company_id = company["id"]
            invitation_data = invitation_stats.get(company_id, {"invited": 0})
            admin = admin_info.get(company_id, {})

            days_since_creation = (
                date.today() - company["creation_date"]
            ).days

            company_data = {
                "company_id": company_id,
                "company_name": company["name"],
                "siren": company["siren"],
                "phone_number": company["phone_number"],
                "nb_employees": company["nb_employees"],
                "invited_employees_count": invitation_data["invited"],
                "admin_email": admin.get("email"),
                "admin_first_name": admin.get("first_name"),
                "admin_last_name": admin.get("last_name"),
                "company_creation_date": company["creation_date"],
                "stage_since_days": days_since_creation,
                "acquisition_status": self._classify_acquisition_stage(
                    {
                        "creation_date": company["creation_date"],
                        "days_since_creation": days_since_creation,
                        "invited_employees": invitation_data["invited"],
                    }
                ),
            }

            acquisition_companies.append(company_data)

        acquisition_companies.sort(
            key=lambda x: x["company_creation_date"], reverse=True
        )
        return acquisition_companies

    def _classify_acquisition_stage(
        self, company_metrics: Dict[str, Any]
    ) -> str:
        """Classify company in acquisition funnel based on creation date and invitations.

        Args:
            company_metrics: Dictionary containing:
                - creation_date: Company creation date
                - days_since_creation: Days since company was created
                - invited_employees: Number of invited employees

        Returns:
            Acquisition stage classification string
        """
        if self._is_new_company_since_march(company_metrics):
            return "Nouvelles entreprises inscrites depuis mars 2025"

        if self._is_no_invite_1_month(company_metrics):
            return "Entreprise inscrite depuis 1 mois sans salarié invité"

        if self._is_no_invite_7_days(company_metrics):
            return "Entreprise inscrite depuis 7 jours sans salarié invité"

        return "Entreprise inscrite"

    def _get_companies_base_data(self) -> List[Dict[str, Any]]:
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
                "siren": self._extract_siren(c.siren_api_info),
                "siret": self._extract_siret(c.siren_api_info),
                "phone_number": c.phone_number,
                "nb_employees": c.number_workers,
                "creation_date": c.creation_time.date(),
            }
            for c in companies
        ]

    def _extract_siren(self, siren_api_info):
        if not siren_api_info or not siren_api_info.get("uniteLegale"):
            return None
        return siren_api_info["uniteLegale"].get("siren")

    def _extract_siret(self, siren_api_info):
        if not siren_api_info or not siren_api_info.get("etablissements"):
            return None
        etablissements = siren_api_info["etablissements"]
        if etablissements:
            return etablissements[-1].get("siret")
        return None

    def _get_invitation_stats(
        self, company_ids: List[int]
    ) -> Dict[int, Dict[str, int]]:
        if not company_ids:
            return {}

        stats = (
            db.session.query(
                Employment.company_id,
                func.count(Employment.user_id).label("invited_count"),
            )
            .filter(
                Employment.company_id.in_(company_ids),
                Employment.validation_status != "rejected",
                Employment.dismissed_at.is_(None),
                Employment.user_id.isnot(None),
            )
            .group_by(Employment.company_id)
            .all()
        )

        return {
            stat.company_id: {"invited": stat.invited_count} for stat in stats
        }

    def _get_admin_info(
        self, company_ids: List[int]
    ) -> Dict[int, Dict[str, str]]:
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

    def _is_new_company_since_march(self, metrics: Dict[str, Any]) -> bool:
        return metrics["creation_date"] >= self.config.NEW_COMPANIES_SINCE_DATE

    def _is_no_invite_1_month(self, metrics: Dict[str, Any]) -> bool:
        return (
            metrics["invited_employees"] == 0
            and metrics["days_since_creation"]
            >= self.config.NO_INVITE_CRITICAL_DAYS
        )

    def _is_no_invite_7_days(self, metrics: Dict[str, Any]) -> bool:
        return (
            metrics["invited_employees"] == 0
            and metrics["days_since_creation"]
            >= self.config.NO_INVITE_WARNING_DAYS
        )


def get_companies_acquisition_data() -> List[Dict[str, Any]]:
    finder = AcquisitionDataFinder()
    return finder.find_companies()


def get_acquisition_companies_excluding_activation() -> tuple[
    List[Dict[str, Any]], List[int]
]:
    """Get acquisition companies excluding those in activation pipeline."""
    from .activation_data_finder import get_companies_activation_data

    activation_companies = get_companies_activation_data()
    activation_company_ids = [c["company_id"] for c in activation_companies]

    finder = AcquisitionDataFinder()
    acquisition_companies = finder.find_companies(
        exclude_company_ids=activation_company_ids
    )

    return acquisition_companies, activation_company_ids
