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

            standalone_employment_ids = (
                self.find_terminated_employments_before_cutoff(
                    cutoff_date, company_ids
                )
            )
            standalone_mission_ids = self.find_missions_before_cutoff(
                cutoff_date
            )

            if self.dry_run:
                all_mission_ids = set(company_mission_ids).union(
                    standalone_mission_ids
                )
                all_employment_ids = set(company_employment_ids).union(
                    standalone_employment_ids
                )
            if not self.dry_run:
                if company_mission_ids:
                    self.anonymize_mission_and_dependencies(
                        company_mission_ids
                    )
                if company_employment_ids:
                    self.anonymize_employment_and_dependencies(
                        company_employment_ids
                    )

                all_mission_ids = set(standalone_mission_ids)
                all_employment_ids = set(standalone_employment_ids)

            if all_mission_ids:
                self.anonymize_mission_and_dependencies(all_mission_ids)
            if all_employment_ids:
                self.anonymize_employment_and_dependencies(all_employment_ids)

            if company_ids:
                self.anonymize_company_and_dependencies(company_ids)

            if not any([company_ids, all_employment_ids, all_mission_ids]):
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

    def delete_anonymized_data(
        self, cutoff_date: datetime, test_mode: bool = False
    ):
        """
        Delete original data that has already been anonymized based on mappings.
        This is used in delete-only mode after a dry run has been verified.

        Args:
            cutoff_date: Date before which data should be deleted (for logging only)
            test_mode: If True, changes will be rolled back at the end
        """
        if test_mode:
            logger.info("Test mode - changes will be rolled back at the end")

        transaction = db.session.begin_nested()
        try:
            mapped_missions = self.get_mapped_ids
            mapped_employments = self.get_mapped_ids("employment")
            mapped_companies = self.get_mapped_ids("company")

            self.log_mapped_data(
                mapped_missions,
                mapped_employments,
                mapped_companies,
                cutoff_date,
            )

            if mapped_missions:
                self.delete_expenditures(mission_ids=mapped_missions)
                self.delete_mission_comments(mapped_missions)
                self.delete_activities(mapped_missions)
                self.delete_mission_ends(mapped_missions)
                self.delete_mission_validations(mapped_missions)
                self.delete_location_entries(mapped_missions)
                self.delete_missions(mapped_missions)

            if mapped_employments:
                self.delete_emails(employment_ids=mapped_employments)
                self.delete_employments(mapped_employments)

            if mapped_companies:
                self.delete_company_team_and_dependencies(mapped_companies)
                self.delete_company_certifications(mapped_companies)
                self.delete_company_stats(mapped_companies)
                self.delete_company_vehicles(mapped_companies)
                self.delete_company_known_addresses(mapped_companies)
                self.delete_companies(mapped_companies)

            if not any(
                [mapped_missions, mapped_employments, mapped_companies]
            ):
                logger.info("No standalone data to delete")
                transaction.rollback()
                return

            if test_mode:
                logger.info("Test mode: rolling back changes")
                transaction.rollback()
                db.session.rollback()
            if not test_mode:
                logger.info("Committing standalone data deletions...")
                transaction.commit()
                db.session.commit()

        except Exception as e:
            logger.error(f"Error deleting standalone data: {e}")
            transaction.rollback()
            db.session.rollback()
            raise

    def log_mapped_data(
        self,
        mission_ids: Set[int],
        activity_ids: Set[int],
        employment_ids: Set[int],
        company_ids: Set[int],
        cutoff_date: datetime,
    ):
        logger.info(f"Found data to delete (cutoff: {cutoff_date.date()}):")

        if company_ids:
            logger.info(f"- {len(company_ids)} companies")
        if employment_ids:
            logger.info(f"- {len(employment_ids)} employments")
        if mission_ids:
            logger.info(f"- {len(mission_ids)} missions")
        if activity_ids:
            logger.info(f"- {len(activity_ids)} activities")

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
            return set()

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
            return set()

        mission_ids = {m.id for m in missions}
        logger.info(f"Found {len(mission_ids)} expired missions to anonymize")
        return mission_ids
