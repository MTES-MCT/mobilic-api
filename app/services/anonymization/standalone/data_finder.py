from app import db
from sqlalchemy import or_, text
from typing import Set, Tuple, Dict, List
from datetime import datetime
from app.services.anonymization.standalone.anonymization_executor import (
    AnonymizationExecutor,
)
from app.models import Mission, Employment, Company, User
from app.models.user import UserAccountStatus
from app.services.anonymization.id_mapping_service import IdMappingService
import logging

logger = logging.getLogger(__name__)


class DataFinder(AnonymizationExecutor):
    def anonymize_standalone_data(
        self, cutoff_date: datetime, test_mode: bool = False
    ):
        """
        Find and anonymize standalone data that has been inactive since cutoff date.

        This method identifies inactive data (companies, missions, employment and anonymized users) and calls
        the executor methods to perform the actual anonymization.

        Args:
            cutoff_date: Date before which data should be anonymized
            test_mode: If True, changes will be rolled back at the end
        """
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

            anonymized_user_ids = self.find_anonymized_users(cutoff_date)

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

            if anonymized_user_ids:
                self.anonymize_user_dependencies(anonymized_user_ids)
                db.session.flush()

            if all_mission_ids:
                self.anonymize_mission_and_dependencies(all_mission_ids)
                db.session.flush()

            if all_employment_ids:
                self.anonymize_employment_and_dependencies(all_employment_ids)
                db.session.flush()

            if company_ids:
                self.anonymize_company_and_dependencies(company_ids)
                db.session.flush()

            if not any(
                [
                    company_ids,
                    all_employment_ids,
                    all_mission_ids,
                    anonymized_user_ids,
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

    def delete_anonymized_data(
        self, cutoff_date: datetime, test_mode: bool = False
    ):
        """
        Find and delete original data that has already been anonymized.

        This method identifies data that has been anonymized (using ID mappings)
        and calls the executor methods to delete the original records. It is used
        in delete-only mode after a dry run has been verified.

        IMPORTANT: Only entities explicitly marked as deletion targets will be deleted.
        This prevents accidental deletion of entities that are only referenced.

        Args:
            cutoff_date: Date before which data should be deleted (for logging only)
            test_mode: If True, changes will be rolled back at the end
        """
        if test_mode:
            logger.info("Test mode - changes will be rolled back at the end")

        transaction = db.session.begin_nested()
        try:
            mapped_missions = IdMappingService.get_deletion_target_ids(
                "mission"
            )
            mapped_employments = IdMappingService.get_deletion_target_ids(
                "employment"
            )
            mapped_companies = IdMappingService.get_deletion_target_ids(
                "company"
            )
            mapped_users = IdMappingService.get_deletion_target_ids("user")

            self.log_mapped_data(
                mapped_missions,
                mapped_employments,
                mapped_companies,
                mapped_users,
                cutoff_date,
            )

            if mapped_missions:
                self.delete_mission_and_dependencies(mapped_missions)

            if mapped_employments:
                self.delete_employment_and_dependencies(mapped_employments)

            if mapped_companies:
                self.delete_company_and_dependencies(mapped_companies)

            if mapped_users:
                self.delete_user_dependencies(mapped_users)

            if not any(
                [
                    mapped_missions,
                    mapped_employments,
                    mapped_companies,
                    mapped_users,
                ]
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
        employment_ids: Set[int],
        company_ids: Set[int],
        anon_user_ids: Set[int],
        cutoff_date: datetime,
    ):
        logger.info(f"Found data to delete (cutoff: {cutoff_date.date()}):")

        if mission_ids:
            logger.info(f"- {len(mission_ids)} missions")
        if employment_ids:
            logger.info(f"- {len(employment_ids)} employments")
        if company_ids:
            logger.info(f"- {len(company_ids)} companies")
        if anon_user_ids:
            logger.info(f"- {len(anon_user_ids)} users")

    def find_inactive_companies_and_dependencies(
        self, cutoff_date: datetime
    ) -> Tuple[Set[int], Set[int], Set[int]]:
        """Find inactive companies and their related data based on:
        - All employments have end_date OR
        - No missions since cutoff_date

        Returns:
            Tuple containing:
            - List of company IDs
            - List of related employment IDs
            - List of related mission IDs
        """
        companies_terminated_employment = (
            self.find_inactive_companies_by_employment(cutoff_date)
        )
        companies_no_recent_missions = (
            self.find_inactive_companies_by_missions(cutoff_date)
        )

        inactive_companies = companies_terminated_employment.union(
            companies_no_recent_missions
        )

        if not inactive_companies:
            logger.info("No companies found matching inactivity criteria")
            return [], [], []

        employments = (
            Employment.query.filter(
                Employment.company_id.in_(inactive_companies)
            )
            .with_entities(Employment.id)
            .all()
        )
        employment_ids = {e[0] for e in employments}

        missions = (
            Mission.query.filter(Mission.company_id.in_(inactive_companies))
            .with_entities(Mission.id)
            .all()
        )
        mission_ids = {m[0] for m in missions}

        company_ids = list(inactive_companies)
        logger.info(f"Found {len(company_ids)} inactive companies:")
        logger.info(
            f"- employments ended: {len(companies_terminated_employment)}"
        )
        logger.info(
            f"- no mission since cutoff date: {len(companies_no_recent_missions)} "
            f"with {len(employment_ids)} related employments "
            f"and {len(mission_ids)} related missions"
        )

        return company_ids, list(employment_ids), list(mission_ids)

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

        companies = (
            Company.query.filter(
                Company.creation_time < cutoff_date,
                ~Company.id.in_(active_companies),
            )
            .with_entities(Company.id)
            .all()
        )

        return {c[0] for c in companies} if companies else set()

    def find_inactive_companies_by_missions(
        self, cutoff_date: datetime
    ) -> Set[int]:
        active_companies = (
            db.session.query(Mission.company_id)
            .filter(Mission.creation_time >= cutoff_date)
            .distinct()
            .subquery()
        )

        companies = (
            Company.query.filter(
                Company.creation_time < cutoff_date,
                ~Company.id.in_(active_companies),
            )
            .with_entities(Company.id)
            .all()
        )

        return {c[0] for c in companies} if companies else set()

    def find_terminated_employments_before_cutoff(
        self, cutoff_date: datetime, exclude_company_ids: Set[int] = None
    ) -> Set[int]:
        """
        Find employments that were terminated before the cutoff date.

        These employments will be marked as deletion targets.

        Args:
            cutoff_date: Date before which employments should be considered
            exclude_company_ids: Optional set of company IDs to exclude

        Returns:
            Set of employment IDs that are terminated and should be anonymized/deleted
        """
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

        employments = query.with_entities(Employment.id).all()
        if not employments:
            logger.info("No terminated employments found")
            return set()

        employment_ids = {e[0] for e in employments}

        logger.info(
            f"Found {len(employment_ids)} terminated employments to anonymize"
        )
        return employment_ids

    def find_missions_before_cutoff(self, cutoff_date: datetime) -> Set[int]:
        """
        Find missions that were created before the cutoff date.

        Args:
            cutoff_date: Date before which missions should be considered

        Returns:
            Set of mission IDs that are expired and should be anonymized
        """
        missions = (
            Mission.query.filter(Mission.creation_time < cutoff_date)
            .with_entities(Mission.id)
            .all()
        )

        if not missions:
            logger.info("No expired missions found")
            return set()

        mission_ids = {m[0] for m in missions}

        logger.info(f"Found {len(mission_ids)} expired missions to anonymize")
        return mission_ids

    def find_anonymized_users(self, cutoff_date: datetime) -> Set[int]:
        """
        Find users that have been anonymized before the cutoff date.

        Note that the users themselves will never be deleted, only anonymized in-place.

        Args:
            cutoff_date: Date before which users should be considered

        Returns:
            Set of user IDs that have been anonymized and whose dependencies should be anonymized
        """
        anon_users = (
            User.query.filter(
                User.creation_time < cutoff_date,
                User.status == UserAccountStatus.ANONYMIZED,
                User.id > 0,
            )
            .with_entities(User.id)
            .all()
        )

        if not anon_users:
            logger.info("No anonymized user found")
            return set()

        anon_users_ids = {user[0] for user in anon_users}

        logger.info(
            f"Found {len(anon_users_ids)} anonymized users with dependencies to anonymize"
        )
        return anon_users_ids
