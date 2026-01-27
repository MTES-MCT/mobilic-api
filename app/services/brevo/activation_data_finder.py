"""Activation funnel data finder."""

from datetime import date
from sqlalchemy import func
from typing import List, Dict, Any, Optional

from app import db
from app.models import Email, Employment, User, Mission, MissionValidation
from app.helpers.mail_type import EmailType
from ._config import BrevoFunnelConfig
from .utils import (
    get_companies_base_data,
    get_admin_info,
    get_creator_activation_status,
)


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
        creator_activation = get_creator_activation_status(company_ids)
        first_mission_dates = self._get_first_mission_validation_dates(company_ids)
        activity_email_status = self._get_activity_email_status(company_ids)

        employment_stats = self._get_employment_stats(company_ids)
        mission_stats = self._get_mission_stats(company_ids)
        admin_info = get_admin_info(company_ids)

        activation_companies = []
        for company in companies_base:
            company_id = company["id"]

            is_creator_active = creator_activation.get(company_id, False)
            if not is_creator_active:
                continue

            emp_stats = employment_stats.get(
                company_id, {"total": 0, "invited": 0}
            )
            mission_count = mission_stats.get(company_id, 0)
            first_mission_date = first_mission_dates.get(company_id)
            email_status = activity_email_status.get(
                company_id, {"has_first_email": False, "has_reminder_email": False}
            )
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
                    "days_since_creation": days_since_creation,
                    "validated_missions": mission_count,
                    "first_mission_date": first_mission_date,
                    "company_creation_date": company["creation_date"],
                    "has_first_email": email_status["has_first_email"],
                    "has_reminder_email": email_status["has_reminder_email"],
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

    def _get_first_mission_validation_dates(
        self, company_ids: List[int]
    ) -> Dict[int, date]:
        if not company_ids:
            return {}

        stats = (
            db.session.query(
                Mission.company_id,
                func.min(MissionValidation.reception_time).label(
                    "first_validation"
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

        return {
            stat.company_id: stat.first_validation.date()
            for stat in stats
            if stat.first_validation
        }

    def _get_activity_email_status(
        self, company_ids: List[int]
    ) -> Dict[int, Dict[str, bool]]:
        if not company_ids:
            return {}

        first_email_stats = (
            db.session.query(Employment.company_id)
            .join(Email, Email.employment_id == Employment.id)
            .filter(
                Employment.company_id.in_(company_ids),
                Email.type == EmailType.COMPANY_WITH_EMPLOYEE_BUT_WITHOUT_ACTIVITY,
            )
            .distinct()
            .all()
        )

        reminder_email_stats = (
            db.session.query(Employment.company_id)
            .join(Email, Email.employment_id == Employment.id)
            .filter(
                Employment.company_id.in_(company_ids),
                Email.type
                == EmailType.COMPANY_WITH_EMPLOYEE_BUT_WITHOUT_ACTIVITY_REMINDER,
            )
            .distinct()
            .all()
        )

        first_email_company_ids = {stat.company_id for stat in first_email_stats}
        reminder_email_company_ids = {
            stat.company_id for stat in reminder_email_stats
        }

        return {
            company_id: {
                "has_first_email": company_id in first_email_company_ids,
                "has_reminder_email": company_id in reminder_email_company_ids,
            }
            for company_id in company_ids
        }

    def _classify_activation_stage(
        self, metrics: Dict[str, Any]
    ) -> Optional[str]:
        days = metrics["days_since_creation"]
        missions = metrics["validated_missions"]
        first_mission_date = metrics.get("first_mission_date")
        company_creation_date = metrics["company_creation_date"]
        has_first_email = metrics.get("has_first_email", False)
        has_reminder_email = metrics.get("has_reminder_email", False)

        if missions >= 1 and first_mission_date:
            days_to_first_mission = (first_mission_date - company_creation_date).days
            if days_to_first_mission <= self.config.ACTIVATION_DEADLINE_DAYS:
                return "gagnée"

        if missions == 0 and days > self.config.ACTIVATION_DEADLINE_DAYS:
            return "perdue"

        if missions == 0:
            if has_reminder_email:
                return "Entreprise sans mission : relancée par mail à J+14"
            if has_first_email and days >= self.config.ACTIVATION_PHONING_J10_DAYS:
                return "Entreprise sans mission à J+10"
            if has_first_email:
                return "Entreprise sans mission : relancée par mail à J+7"
            return "Entreprise avec compte activé ayant 0 mission"

        return None


def get_companies_activation_data() -> List[Dict[str, Any]]:
    finder = ActivationDataFinder()
    return finder.find_companies()
