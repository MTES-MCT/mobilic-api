from app import db
from typing import List
from datetime import datetime, timedelta
from app.models import Activity, ActivityVersion, Mission
from app.models.anonymized import (
    ActivityAnonymized,
    ActivityVersionAnonymized,
    MissionAnonymized,
    IdMapping,
)
from app.services.table_dependency_manager import TableDependencyManager
import logging

logger = logging.getLogger(__name__)


def migrate_anonymized_data(verbose=False, test_mode=False):
    if verbose:
        logger.setLevel(logging.DEBUG)

    dependency_manager = TableDependencyManager(db.session)
    anonymizer = TableAnonymizer(db.session)

    transaction = db.session.begin_nested()
    try:
        logger.info("Clearing ID mapping table...")
        IdMapping.query.delete()

        cutoff_date = datetime.now() - timedelta(days=365)
        logger.info(f"Processing data older than: {cutoff_date}")

        anonymization_order = dependency_manager.get_anonymization_order()

        for level_tables in anonymization_order:
            for table_name in level_tables:
                logger.info(f"Anonymizing table: {table_name}")

                if table_name == "mission":
                    anonymizer.anonymize_mission(cutoff_date)
                elif table_name == "activity":
                    anonymizer.anonymize_activities_for_missions([])
                elif table_name == "activity_version":
                    pass

        logger.info("Cleaning up ID mapping table...")
        IdMapping.query.delete()

        if test_mode:
            logger.info("Test mode: rolling back all changes")
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

    def anonymize_activities_for_missions(self, mission_ids: List[int]):
        """
        Anonymize all activities linked to specified missions, regardless of their creation date
        to maintain data consistency
        """
        activities = Activity.query.filter(
            Activity.mission_id.in_(mission_ids)
        ).all()

        if not activities:
            logger.info("No activities found for these missions")
            return

        logger.info(
            f"Found {len(activities)} activities linked to missions to anonymize"
        )
        activity_ids = [a.id for a in activities]

        activity_versions = ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).all()

        logger.info(
            f"Found {len(activity_versions)} activity versions to anonymize"
        )

        for activity_version in activity_versions:
            anonymized = ActivityVersionAnonymized.anonymize(activity_version)
            self.db.add(anonymized)

        logger.info(
            f"Deleting {len(activity_ids)} original activities_version"
        )
        ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).delete(synchronize_session=False)

        logger.info("Processing activities...")
        for activity in activities:
            anonymized = ActivityAnonymized.anonymize(activity)
            self.db.add(anonymized)

        logger.info(f"Deleting {len(activity_ids)} original activities")
        Activity.query.filter(Activity.id.in_(activity_ids)).delete(
            synchronize_session=False
        )

    def anonymize_mission(self, cutoff_date: datetime) -> List[int]:
        """
        Anonymize missions older than cutoff_date and all their related data
        """
        try:
            missions_to_migrate = Mission.query.filter(
                Mission.creation_time < cutoff_date
            ).all()

            if not missions_to_migrate:
                logger.info("No missions to anonymize")
                return []

            logger.info(
                f"Found {len(missions_to_migrate)} missions to anonymize"
            )
            mission_ids = [m.id for m in missions_to_migrate]

            logger.info("Processing activities linked to missions...")
            self.anonymize_activities_for_missions(mission_ids)

            logger.info("Processing missions...")
            for mission in missions_to_migrate:
                anonymized = MissionAnonymized.anonymize(mission)
                self.db.add(anonymized)

            logger.info(f"Deleting {len(mission_ids)} original missions")
            Mission.query.filter(Mission.id.in_(mission_ids)).delete(
                synchronize_session=False
            )

            logger.info("Mission anonymization completed")
            return mission_ids

        except Exception as e:
            logger.error(f"Error anonymizing missions: {e}")
            raise
