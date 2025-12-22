"""Acquisition funnel data finder."""

from datetime import date
from typing import List, Dict, Any

from ._config import BrevoFunnelConfig
from .utils import (
    get_companies_base_data,
    get_admin_info,
    get_creator_activation_status,
)


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
        companies_base = get_companies_base_data()
        if not companies_base:
            return []

        if exclude_company_ids:
            companies_base = [
                c for c in companies_base if c["id"] not in exclude_company_ids
            ]

        company_ids = [c["id"] for c in companies_base]

        creator_activation = get_creator_activation_status(company_ids)
        admin_info = get_admin_info(company_ids)

        acquisition_companies = []
        for company in companies_base:
            company_id = company["id"]
            is_creator_active = creator_activation.get(company_id, False)
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
                "active_employees_count": 1 if is_creator_active else 0,
                "admin_email": admin.get("email"),
                "admin_first_name": admin.get("first_name"),
                "admin_last_name": admin.get("last_name"),
                "company_creation_date": company["creation_date"],
                "stage_since_days": days_since_creation,
                "acquisition_status": self._classify_acquisition_stage(
                    {
                        "is_creator_active": is_creator_active,
                        "days_since_creation": days_since_creation,
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
        """Classify company in acquisition funnel based on creator activation.

        Classification is based only on the company creator's account status.

        Classification logic (priority order):
        1. Creator has activated their account → WON
        2. 14+ days since creation without creator activation → LOST
        3. New company without creator activation → REGISTERED (default)

        Args:
            company_metrics: Dictionary containing:
                - is_creator_active: Boolean indicating if creator account is active
                - days_since_creation: Days since company was created

        Returns:
            Acquisition stage classification string
        """
        if company_metrics["is_creator_active"]:
            return "gagnée : entreprise inscrite avec compte (1er gestionnaire) activé"

        if (
            company_metrics["days_since_creation"]
            >= self.config.ACCOUNT_ACTIVATION_DEADLINE_DAYS
        ):
            return "perdue : entreprise qui n'active pas son compte au bout de 2 semaines"

        # TODO: Add reminder email status check when ticket is implemented
        # Ticket: https://trello.com/c/2Q0k0kzu/2174
        # if company_metrics.get("has_reminder_email", False):
        #     return "entreprise inscrite sans compte activé relancée par mail j+2"

        return "entreprise inscrite sans compte activé"


def get_companies_acquisition_data() -> List[Dict[str, Any]]:
    finder = AcquisitionDataFinder()
    return finder.find_companies()
