from app import app, db
from typing import List
from datetime import datetime
from dateutil.relativedelta import relativedelta
from app.models import (
    Activity,
    ActivityVersion,
    Mission,
    Company,
    MissionEnd,
    MissionValidation,
    LocationEntry,
    Expenditure,
    Employment,
    Email,
)
from app.models.anonymized import (
    IdMapping,
    ActivityAnonymized,
    ActivityVersionAnonymized,
    MissionAnonymized,
    MissionEndAnonymized,
    MissionValidationAnonymized,
    LocationEntryAnonymized,
    EmploymentAnonymized,
    EmailAnonymized,
    # CompanyAnonymized
)

# from app.services.table_dependency_manager import TableDependencyManager
import logging

logger = logging.getLogger(__name__)

""" 
priority order and dependancies with mission as reference point
    mission
      ├─ activity
      │   └─ activity_version
      ├─ mission_end
      ├─ mission_validation
      ├─ location_entry
      │   ├─ address
      │   └─ company_known_address
      |- expenditure => no need to anonymize, only delete
      └─ company => todo
          ├─ company_certification => todo
          ├─ company_stats => todo
          └─ business => todo

priority order and dependancies with memployement as reference point
    employement => only get the one with end_date not null
      └─ email
"""

years = app.config["NUMBER_OF_YEAR_TO_SUBSTRACT_FOR_ANONYMISATION"]


def migrate_anonymized_data(verbose=False, test_mode=False):
    if verbose:
        logger.setLevel(logging.DEBUG)

    anonymizer = TableAnonymizer(db.session)

    transaction = db.session.begin_nested()
    try:
        IdMapping.query.delete()
        cutoff_date = datetime.now() - relativedelta(years=years)

        mission_ids = anonymizer.get_missions_to_anonymize(cutoff_date)
        if mission_ids:
            anonymizer.process_activities(mission_ids)
            anonymizer.process_mission_ends(mission_ids)
            anonymizer.process_mission_validations(mission_ids)
            anonymizer.process_location_entries(mission_ids)
            anonymizer.delete_expenditures(mission_ids)
            anonymizer.process_missions(mission_ids)
        else:
            logger.info("No missions to anonymize")

        employment_ids = anonymizer.get_employments_to_anonymize(cutoff_date)
        if employment_ids:
            anonymizer.process_emails(employment_ids)
            anonymizer.process_employments(employment_ids)
        else:
            logger.info("No employments to anonymize")

        if test_mode:
            logger.info("Test mode: rolling back changes")
            transaction.rollback()
        else:
            logger.info("Committing changes...")
            transaction.commit()

    except Exception as e:
        logger.error(f"Error during anonymization: {e}")
        transaction.rollback()
        raise


class TableAnonymizer:
    def __init__(self, db_session):
        self.db = db_session
        self.processed_ids = {}

    def get_missions_to_anonymize(self, cutoff_date: datetime) -> List[int]:
        """Get missions to anonymize based on cutoff date"""
        missions = Mission.query.filter(
            Mission.creation_time < cutoff_date
        ).all()

        if not missions:
            return []

        mission_ids = [m.id for m in missions]
        logger.info(f"Found {len(mission_ids)} missions to anonymize")
        return mission_ids

    def process_activities(self, mission_ids: List[int]) -> List[int]:
        """Process activities and their versions"""
        activities = Activity.query.filter(
            Activity.mission_id.in_(mission_ids)
        ).all()

        if not activities:
            logger.info("No activities found for these missions")
            return []

        activity_ids = [a.id for a in activities]

        # Process activity versions first
        self.process_activity_versions(activity_ids)

        logger.info(f"Processing {len(activities)} activities...")
        for activity in activities:
            anonymized = ActivityAnonymized.anonymize(activity)
            self.db.add(anonymized)

        Activity.query.filter(Activity.id.in_(activity_ids)).delete(
            synchronize_session=False
        )

        return activity_ids

    def process_activity_versions(self, activity_ids: List[int]):
        """Process activity versions for given activities"""
        activity_versions = ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).all()

        if not activity_versions:
            logger.info("No activity versions found")
            return

        logger.info(
            f"Processing {len(activity_versions)} activity versions..."
        )

        for version in activity_versions:
            anonymized = ActivityVersionAnonymized.anonymize(version)
            self.db.add(anonymized)

        ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).delete(synchronize_session=False)

    def process_mission_ends(self, mission_ids: List[int]):
        """Process mission ends"""
        mission_ends = MissionEnd.query.filter(
            MissionEnd.mission_id.in_(mission_ids)
        ).all()

        if not mission_ends:
            logger.info("No mission ends found")
            return

        logger.info(f"Processing {len(mission_ends)} mission ends...")
        for mission_end in mission_ends:
            anonymized = MissionEndAnonymized.anonymize(mission_end)
            self.db.add(anonymized)

        MissionEnd.query.filter(MissionEnd.mission_id.in_(mission_ids)).delete(
            synchronize_session=False
        )

    def process_mission_validations(self, mission_ids: List[int]):
        """Process mission validations"""
        validations = MissionValidation.query.filter(
            MissionValidation.mission_id.in_(mission_ids)
        ).all()

        if not validations:
            logger.info("No mission validations found")
            return

        logger.info(f"Processing {len(validations)} mission validations...")
        for validation in validations:
            anonymized = MissionValidationAnonymized.anonymize(validation)
            self.db.add(anonymized)

        MissionValidation.query.filter(
            MissionValidation.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

    def process_location_entries(self, mission_ids: List[int]):
        """Process location entries"""
        entries = LocationEntry.query.filter(
            LocationEntry.mission_id.in_(mission_ids)
        ).all()

        if not entries:
            logger.info("No location entries found")
            return

        logger.info(f"Processing {len(entries)} location entries...")
        for entry in entries:
            anonymized = LocationEntryAnonymized.anonymize(entry)
            self.db.add(anonymized)

        LocationEntry.query.filter(
            LocationEntry.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

    def delete_expenditures(self, mission_ids: List[int]):
        """Delete expenditures"""
        deleted = Expenditure.query.filter(
            Expenditure.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        if deleted:
            logger.info(f"Deleted {deleted} expenditures")

    def process_missions(self, mission_ids: List[int]):
        """Process missions after all dependencies are handled"""
        missions = Mission.query.filter(Mission.id.in_(mission_ids)).all()

        logger.info(f"Processing {len(missions)} missions...")
        for mission in missions:
            anonymized = MissionAnonymized.anonymize(mission)
            self.db.add(anonymized)

        Mission.query.filter(Mission.id.in_(mission_ids)).delete(
            synchronize_session=False
        )

    def get_employments_to_anonymize(self, cutoff_date: datetime) -> List[int]:
        """Get employments to anonymize based on cutoff date and ended status"""
        employments = Employment.query.filter(
            Employment.creation_time < cutoff_date,
            Employment.end_date.isnot(None),
        ).all()

        if not employments:
            return []

        employment_ids = [e.id for e in employments]
        logger.info(f"Found {len(employment_ids)} employments to anonymize")
        return employment_ids

    def process_employments(self, employment_ids: List[int]):
        """Process employments"""
        employments = Employment.query.filter(
            Employment.id.in_(employment_ids)
        ).all()

        if not employments:
            logger.info("No employments found")
            return

        logger.info(f"Processing {len(employments)} employments...")
        for employment in employments:
            anonymized = EmploymentAnonymized.anonymize(employment)
            self.db.add(anonymized)

        Employment.query.filter(Employment.id.in_(employment_ids)).delete(
            synchronize_session=False
        )

    def process_emails(self, employment_ids: List[int]):
        """Process emails linked to employments"""
        emails = Email.query.filter(
            Email.employment_id.in_(employment_ids)
        ).all()

        if not emails:
            logger.info("No emails found")
            return

        logger.info(f"Processing {len(emails)} emails...")
        for email in emails:
            anonymized = EmailAnonymized.anonymize(email)
            self.db.add(anonymized)

        Email.query.filter(Email.employment_id.in_(employment_ids)).delete(
            synchronize_session=False
        )
