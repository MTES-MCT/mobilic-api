"""Acquisition funnel data finder."""

from datetime import date
from sqlalchemy import func
from typing import List, Dict, Any

from app import db
from app.models import Employment, User
from app.models.user import UserAccountStatus
from ._config import BrevoFunnelConfig
from .utils import get_companies_base_data, get_admin_info


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

        active_employees_stats = self._get_active_employees_stats(company_ids)
        admin_info = get_admin_info(company_ids)

        acquisition_companies = []
        for company in companies_base:
            company_id = company["id"]
            active_stats = active_employees_stats.get(
                company_id, {"active_employees": 0}
            )
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
                "active_employees_count": active_stats["active_employees"],
                "admin_email": admin.get("email"),
                "admin_first_name": admin.get("first_name"),
                "admin_last_name": admin.get("last_name"),
                "company_creation_date": company["creation_date"],
                "stage_since_days": days_since_creation,
                "acquisition_status": self._classify_acquisition_stage(
                    {
                        "active_employees_count": active_stats[
                            "active_employees"
                        ],
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
        """Classify company in acquisition funnel based on account activation.

        Classification logic (priority order):
        1. Companies with at least one active employee account
        2. Companies 14+ days old with no active accounts
        3. New companies with no active accounts (default)

        Args:
            company_metrics: Dictionary containing:
                - active_employees_count: Number of employees with active accounts
                - days_since_creation: Days since company was created

        Returns:
            Acquisition stage classification string
        """
        if company_metrics["active_employees_count"] > 0:
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

    def _get_active_employees_stats(
        self, company_ids: List[int]
    ) -> Dict[int, Dict[str, int]]:
        """Get active employee statistics excluding company creators.

        The company creator is identified as the first admin (earliest employment ID).
        This avoids counting the initial admin who created the company as an "active employee".

        Args:
            company_ids: List of company IDs to get stats for

        Returns:
            Dictionary mapping company_id to {"active_employees": count}
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

        return {
            stat.company_id: {"active_employees": stat.active_count}
            for stat in stats
        }


def get_companies_acquisition_data() -> List[Dict[str, Any]]:
    finder = AcquisitionDataFinder()
    return finder.find_companies()
