from app import db
from sqlalchemy import or_
from typing import Set, Tuple
from datetime import datetime
from app.services.anonymization.base import BaseAnonymizer
from app.models import Mission, Employment, Company
import logging

logger = logging.getLogger(__name__)


class StandaloneAnonymizer(BaseAnonymizer):
    def anonymize_standalone_data(
        self, cutoff_date: datetime, test_mode: bool = False
    ):
        transaction = db.session.begin_nested()
        try:
            (
                company_ids,
                company_employment_ids,
                company_mission_ids,
            ) = self.find_inactive_companies_and_dependencies(cutoff_date)

            if company_mission_ids:
                self.anonymize_mission_and_dependencies(company_mission_ids)

            if company_employment_ids:
                self.anonymize_employment_and_dependencies(
                    company_employment_ids
                )

            if company_ids:
                self.anonymize_company_and_dependencies(company_ids)

            standalone_employment_ids = (
                self.find_terminated_employments_before_cutoff(
                    cutoff_date, company_ids
                )
            )
            if standalone_employment_ids:
                self.anonymize_employment_and_dependencies(
                    standalone_employment_ids
                )

            standalone_mission_ids = self.find_missions_before_cutoff(
                cutoff_date
            )
            if standalone_mission_ids:
                self.anonymize_mission_and_dependencies(standalone_mission_ids)

            if not any(
                [
                    company_ids,
                    company_employment_ids,
                    company_mission_ids,
                    standalone_employment_ids,
                    standalone_mission_ids,
                ]
            ):
                logger.info("No standalone data to anonymize")
                transaction.rollback()
                return

            if test_mode:
                logger.info("Test mode: rolling back changes")
                transaction.rollback()
                db.session.rollback()
            if not test_mode:
                logger.info("Committing standalone data changes...")
                transaction.commit()
                db.session.commit()

        except Exception as e:
            logger.error(f"Error processing standalone data: {e}")
            transaction.rollback()
            db.session.rollback()
            raise

    def find_inactive_companies_and_dependencies(
        self, cutoff_date: datetime
    ) -> Tuple[Set[int], Set[int], Set[int]]:
        """Find inactive companies and their related data based on:
        - SIREN API status is 'C' (ceased) OR
        - All employments have end_date OR
        - No missions since cutoff_date
        """
        companies_ceased_siren = self.find_inactive_companies_by_siren(
            cutoff_date
        )
        companies_ceased_employment = (
            self.find_inactive_companies_by_employment(cutoff_date)
        )
        companies_no_recent_missions = (
            self.find_inactive_companies_by_missions(cutoff_date)
        )

        inactive_companies = companies_ceased_siren.union(
            companies_ceased_employment, companies_no_recent_missions
        )

        if not inactive_companies:
            logger.info("No companies found matching inactivity criteria")
            return [], [], []

        employments = Employment.query.filter(
            Employment.company_id.in_(inactive_companies)
        ).all()
        employment_ids = {e.id for e in employments}

        missions = Mission.query.filter(
            Mission.company_id.in_(inactive_companies)
        ).all()
        mission_ids = {m.id for m in missions}

        company_ids = list(inactive_companies)
        logger.info(
            f"Found {len(company_ids)} inactive companies "
            f"(SIREN ceased: {len(companies_ceased_siren)}, "
            f"employments ended: {len(companies_ceased_employment)}, "
            f"no mission since cutoff date : {len(companies_no_recent_missions)}) "
            f"with {len(employment_ids)} related employments "
            f"and {len(mission_ids)} related missions"
        )

        return company_ids, list(employment_ids), list(mission_ids)

    def find_inactive_companies_by_siren(
        self, cutoff_date: datetime
    ) -> Set[int]:
        company_ids = (
            db.session.query(Company.id)
            .filter(
                Company.creation_time < cutoff_date,
                Company.siren_api_info["uniteLegale"][
                    "etatAdministratifUniteLegale"
                ].astext
                == "C",
            )
            .all()
        )
        return {id[0] for id in company_ids}

    def find_inactive_companies_by_employment(
        self, cutoff_date: datetime
    ) -> Set[int]:
        active_companies = (
            db.session.query(Employment.company_id)
            .filter(
                or_(
                    Employment.end_date.is_(None),
                    Employment.dismissed_at.is_(None),
                )
            )
            .distinct()
            .subquery()
        )

        companies = Company.query.filter(
            Company.creation_time < cutoff_date,
            ~Company.id.in_(active_companies),
        ).all()

        return {c.id for c in companies} if companies else set()

    def find_inactive_companies_by_missions(
        self, cutoff_date: datetime
    ) -> Set[int]:
        active_companies = (
            db.session.query(Mission.company_id)
            .filter(Mission.creation_time >= cutoff_date)
            .distinct()
            .subquery()
        )

        companies = Company.query.filter(
            Company.creation_time < cutoff_date,
            ~Company.id.in_(active_companies),
        ).all()

        return {c.id for c in companies} if companies else set()

    def find_terminated_employments_before_cutoff(
        self, cutoff_date: datetime, exclude_company_ids: Set[int] = None
    ) -> Set[int]:
        query = Employment.query.filter(
            Employment.creation_time < cutoff_date,
            or_(
                Employment.end_date.isnot(None),
                Employment.dismissed_at.isnot(None),
            ),
        )

        if exclude_company_ids:
            query = query.filter(
                ~Employment.company_id.in_(exclude_company_ids)
            )

        employments = query.all()
        if not employments:
            logger.info("No terminated employments found")
            return {}

        employment_ids = {e.id for e in employments}
        logger.info(
            f"Found {len(employment_ids)} terminated employments to anonymize"
        )
        return employment_ids

    def find_missions_before_cutoff(self, cutoff_date: datetime) -> Set[int]:
        missions = Mission.query.filter(
            Mission.creation_time < cutoff_date
        ).all()

        if not missions:
            logger.info("No expired missions found")
            return {}

        mission_ids = {m.id for m in missions}
        logger.info(f"Found {len(mission_ids)} expired missions to anonymize")
        return mission_ids
