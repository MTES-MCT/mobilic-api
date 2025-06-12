"""Activation funnel data finder."""

from datetime import date
from sqlalchemy import func
from typing import List, Dict, Any, Optional

from app import db
from app.models import Employment, User, Mission, MissionValidation
from ._config import BrevoFunnelConfig
from .utils import get_companies_base_data, get_admin_info


class ActivationDataFinder:
    """Data finder for activation funnel companies."""

    def __init__(self):
        self.config = BrevoFunnelConfig()

    def find_companies(self) -> List[Dict[str, Any]]:
        """Find companies for activation funnel with strict criteria.

        Returns:
            List of dictionaries containing company data with activation metrics:
            - company_id: Company identifier
            - company_name: Company name
            - activation_status: Funnel stage classification
            - invitation_percentage: Percentage of employees invited
            - validated_missions_count: Number of validated missions
        """

        companies_base = get_companies_base_data()
        if not companies_base:
            return []

        company_ids = [c["id"] for c in companies_base]

        employment_stats = self._get_employment_stats(company_ids)
        mission_stats = self._get_mission_stats(company_ids)
        admin_info = get_admin_info(company_ids)

        activation_companies = []
        for company in companies_base:
            company_id = company["id"]

            emp_stats = employment_stats.get(
                company_id, {"total": 0, "invited": 0}
            )
            mission_count = mission_stats.get(company_id, 0)
            admin = admin_info.get(company_id, {})

            declared_employees = company["nb_employees"] or 0
            calculated_employees = emp_stats["total"]

            total_employees = (
                declared_employees
                if declared_employees > 0
                else calculated_employees
            )
            invited_employees = emp_stats["invited"]

            invitation_percentage = 0.0
            if total_employees > 0:
                invitation_percentage = round(
                    (invited_employees / total_employees) * 100, 2
                )

            days_since_creation = (
                date.today() - company["creation_date"]
            ).days

            activation_status = self._classify_activation_stage(
                {
                    "total_employees": total_employees,
                    "invited_employees": invited_employees,
                    "invitation_percentage": invitation_percentage,
                    "validated_missions": mission_count,
                }
            )

            if activation_status is None:
                continue

            activation_companies.append(
                {
                    "company_id": company_id,
                    "company_name": company["name"],
                    "siren": company["siren"],
                    "phone_number": company["phone_number"],
                    "nb_employees": company["nb_employees"],
                    "total_employees_count": total_employees,
                    "invited_employees_count": invited_employees,
                    "invitation_percentage": invitation_percentage,
                    "validated_missions_count": mission_count,
                    "admin_email": admin.get("email"),
                    "admin_first_name": admin.get("first_name"),
                    "admin_last_name": admin.get("last_name"),
                    "company_creation_date": company["creation_date"],
                    "activation_status": activation_status,
                    "stage_since_days": days_since_creation,
                }
            )

        activation_companies.sort(
            key=lambda x: (
                x["invitation_percentage"],
                x["validated_missions_count"],
            ),
            reverse=True,
        )
        return activation_companies

    def _get_employment_stats(
        self, company_ids: List[int]
    ) -> Dict[int, Dict[str, int]]:
        if not company_ids:
            return {}

        stats = (
            db.session.query(
                Employment.company_id,
                func.count("*").label("total_count"),
                func.count(Employment.user_id).label("invited_count"),
            )
            .filter(
                Employment.company_id.in_(company_ids),
                Employment.validation_status != "rejected",
                Employment.dismissed_at.is_(None),
            )
            .group_by(Employment.company_id)
            .all()
        )

        return {
            stat.company_id: {
                "total": stat.total_count,
                "invited": stat.invited_count,
            }
            for stat in stats
        }

    def _get_mission_stats(self, company_ids: List[int]) -> Dict[int, int]:
        if not company_ids:
            return {}

        stats = (
            db.session.query(
                Mission.company_id,
                func.count(func.distinct(MissionValidation.mission_id)).label(
                    "validated_count"
                ),
            )
            .join(
                MissionValidation, Mission.id == MissionValidation.mission_id
            )
            .filter(
                Mission.company_id.in_(company_ids),
                MissionValidation.is_admin == True,
            )
            .group_by(Mission.company_id)
            .all()
        )

        return {stat.company_id: stat.validated_count for stat in stats}

    def _classify_activation_stage(
        self, metrics: Dict[str, Any]
    ) -> Optional[str]:
        """Classify company in activation funnel with strict criteria.

        Args:
            metrics: Dictionary containing company metrics:
                - total_employees: Total number of employees
                - invited_employees: Number of invited employees
                - invitation_percentage: Percentage of employees invited
                - validated_missions: Number of validated missions

        Returns:
            Activation stage classification string or None if doesn't qualify
        """

        if metrics["total_employees"] == 0:
            return

        if metrics["invited_employees"] == 0:
            return

        if self._is_full_activation(metrics):
            return "Entreprise ayant invité 100% de leurs salariés + au moins 1 mission validée par le gestionnaire"

        if self._is_complete_activation_no_mission(metrics):
            return "Entreprise ayant invité entre 80 et 100% de leurs salariés + 0 mission validée"

        if self._is_mid_activation(metrics):
            return "Entreprise ayant invité entre 30 et 80% de leurs salariés + 0 mission validée"

        if self._is_low_activation(metrics):
            return "Entreprise ayant invité moins de 30% de leurs salariés + 0 mission validée"

    def _is_full_activation(self, metrics: Dict[str, Any]) -> bool:
        return (
            metrics["total_employees"] > 0
            and metrics["invitation_percentage"] >= 100
            and metrics["validated_missions"] >= 1
        )

    def _is_complete_activation_no_mission(
        self, metrics: Dict[str, Any]
    ) -> bool:
        return (
            metrics["total_employees"] > 0
            and self.config.HIGH_INVITATION_THRESHOLD
            < metrics["invitation_percentage"]
            < self.config.COMPLETE_INVITATION_THRESHOLD
            and metrics["validated_missions"] == 0
        )

    def _is_mid_activation(self, metrics: Dict[str, Any]) -> bool:
        return (
            metrics["total_employees"] > 0
            and self.config.LOW_INVITATION_THRESHOLD
            <= metrics["invitation_percentage"]
            <= self.config.HIGH_INVITATION_THRESHOLD
            and metrics["validated_missions"] == 0
        )

    def _is_low_activation(self, metrics: Dict[str, Any]) -> bool:
        return (
            metrics["total_employees"] > 0
            and metrics["invitation_percentage"]
            < self.config.LOW_INVITATION_THRESHOLD
            and metrics["validated_missions"] == 0
        )


def get_companies_activation_data() -> List[Dict[str, Any]]:
    finder = ActivationDataFinder()
    return finder.find_companies()
