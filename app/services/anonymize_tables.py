from app import app, db
import itertools
from typing import List, Optional
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
    Comment,
    Employment,
    Email,
    User,
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
    UserAnonymized,
    # CompanyAnonymized
)

import logging

logger = logging.getLogger(__name__)

""" 
priority order and dependancies with user as reference point
    user
      ├─ activity
      │   └─ activity_version
      ├─ comment
      ├─ company_known_address
      │   └─ team_known_address
      ├─ controller_control
      ├─ email (lié à employment)
      ├─ employment
      │   └─ third_party_client_employment
      ├─ expenditure
      ├─ location_entry
      ├─ mission
      │   ├─ activity
      │   │   └─ activity_version
      │   ├─ mission_end
      │   ├─ mission_validation
      │   ├─ location_entry
      │   └─ expenditure
      ├─ oauth2_authorization_code
      ├─ oauth2_token
      ├─ refresh_token
      ├─ regulation_computation
      ├─ regulatory_alert
      ├─ scenario_testing
      ├─ team_admin_user
      ├─ third_party_client_company
      ├─ user_agreement
      ├─ user_read_token
      ├─ user_survey_actions
      └─ vehicle
          ├─ activity
          ├─ comment
          ├─ expenditure
          ├─ location_entry
          ├─ mission
          ├─ mission_end
          ├─ mission_validation
          └─ team_vehicle

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
    employement => only with end_date not null
      └─ email
"""

years = app.config["NUMBER_OF_YEAR_TO_SUBSTRACT_FOR_ANONYMISATION"]
batch_size = app.config["USER_BATCH_SIZE_FOR_ANONYMISATION"]


def migrate_anonymized_data(verbose=False, test_mode=False):
    if verbose:
        logger.setLevel(logging.DEBUG)

    anonymizer = TableAnonymizer(db.session)

    try:
        IdMapping.query.delete()
        cutoff_date = datetime.now() - relativedelta(years=years)

        user_generator = anonymizer.get_users_to_anonymize(
            cutoff_date, batch_size=batch_size
        )

        first_batch = list(itertools.islice(user_generator, 1))

        if first_batch:
            all_batches = itertools.chain(first_batch, user_generator)
            anonymizer.process_with_users(cutoff_date, test_mode, all_batches)
        else:
            anonymizer.process_without_users(cutoff_date, test_mode)

    except Exception as e:
        logger.error(f"Error during anonymization: {e}")
        raise


class TableAnonymizer:
    def __init__(self, db_session):
        self.db = db_session
        self.processed_ids = {}

    def process_with_users(
        self, cutoff_date: datetime, test_mode: bool, user_batches
    ):
        for user_batch in user_batches:
            transaction = db.session.begin_nested()
            try:
                logger.info(f"Processing batch of {len(user_batch)} users...")

                mission_ids = self.get_missions_to_anonymize(
                    user_ids=user_batch
                )
                if mission_ids:
                    self.process_activities(mission_ids)
                    self.process_mission_ends(mission_ids)
                    self.process_mission_validations(mission_ids)
                    self.process_location_entries(mission_ids)
                    self.delete_expenditures(mission_ids)
                    self.delete_comments(mission_ids)
                    self.process_missions(mission_ids)

                employment_ids = self.get_employments_to_anonymize(
                    cutoff_date, user_batch
                )
                if employment_ids:
                    self.process_emails(employment_ids)
                    self.process_employments(employment_ids)

                self.process_users(user_batch)

                if test_mode:
                    logger.info("Test mode: rolling back batch")
                    transaction.rollback()
                else:
                    logger.info(
                        f"Committing batch of {len(user_batch)} users..."
                    )
                    transaction.commit()

            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                transaction.rollback()
                raise

    def process_without_users(self, cutoff_date: datetime, test_mode: bool):
        logger.info(
            "No users to anonymize, checking for standalone missions and employments..."
        )
        transaction = db.session.begin_nested()
        try:
            mission_ids = self.get_missions_to_anonymize(
                cutoff_date=cutoff_date
            )
            employment_ids = self.get_employments_to_anonymize(cutoff_date)

            if not mission_ids and not employment_ids:
                logger.info("No data to anonymize")
                transaction.rollback()
                return

            if mission_ids:
                self.process_activities(mission_ids)
                self.process_mission_ends(mission_ids)
                self.process_mission_validations(mission_ids)
                self.process_location_entries(mission_ids)
                self.delete_expenditures(mission_ids)
                self.process_missions(mission_ids)

            if employment_ids:
                self.process_emails(employment_ids)
                self.process_employments(employment_ids)

            if test_mode:
                logger.info("Test mode: rolling back changes")
                transaction.rollback()
            else:
                logger.info("Committing standalone data changes...")
                transaction.commit()

        except Exception as e:
            logger.error(f"Error processing standalone data: {e}")
            transaction.rollback()
            raise

    from typing import List, Optional

    def get_missions_to_anonymize(
        self,
        cutoff_date: Optional[datetime] = None,
        user_ids: Optional[List[int]] = None,
    ) -> List[int]:
        if cutoff_date and not isinstance(cutoff_date, datetime):
            raise ValueError("cutoff_date must be a datetime object")
        if user_ids and not isinstance(user_ids, list):
            raise ValueError("user_ids must be a list of integers")

        query = Mission.query
        if cutoff_date:
            query = query.filter(Mission.creation_time < cutoff_date)
        if user_ids:
            query = query.filter(Mission.submitter_id.in_(user_ids))

        missions = query.all()

        mission_ids_to_anonymize = []
        for mission in missions:
            has_active_participants = (
                Activity.query.filter(
                    Activity.mission_id == mission.id,
                    Activity.user_id.notin_(user_ids or []),
                ).count()
                > 0
            )

            if not has_active_participants:
                mission_ids_to_anonymize.append(mission.id)

        if not mission_ids_to_anonymize:
            logger.info("No missions found to anonymize")
            return []

        logger.info(
            f"Found {len(mission_ids_to_anonymize)} missions to anonymize"
        )
        return mission_ids_to_anonymize

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
        deleted = Expenditure.query.filter(
            Expenditure.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        if deleted:
            logger.info(f"Deleted {deleted} expenditures")

    def delete_comments(self, mission_ids: List[int]):
        deleted = Comment.query.filter(
            Comment.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        if deleted:
            logger.info(f"Deleted {deleted} comment")

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

    def get_employments_to_anonymize(
        self, cutoff_date: datetime, user_ids: List[int] = None
    ) -> List[int]:
        """
        Get employement to anonymize based on :
        - cutoff_date
        - employement is terminated : end_date not null
        - optionnaly, a specific list of user ids
        """
        query = Employment.query.filter(
            Employment.creation_time < cutoff_date,
            Employment.end_date.isnot(None),
        )

        if user_ids:
            query = query.filter(Employment.user_id.in_(user_ids))

        employments = query.all()

        if not employments:
            logger.info(
                "No employments found to anonymize"
                + (" for specified users" if user_ids else "")
            )
            return []

        employment_ids = [e.id for e in employments]
        logger.info(
            f"Found {len(employment_ids)} employments to anonymize"
            + (" for specified users" if user_ids else "")
        )

        return employment_ids

    def process_employments(self, employment_ids: List[int]):
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

    def get_users_to_anonymize(self, cutoff_date: datetime, batch_size: int):
        """
        Get users to anonymize by batch based on:
            - cutoff date AND (
                - all employments terminated;
                - OR no missions since cutoff date
            )
        """
        users_with_active_employments = (
            db.session.query(Employment.user_id)
            .filter(Employment.end_date.is_(None))
            .distinct()
            .cte("active_employments")
        )

        recent_missions = (
            db.session.query(Mission.submitter_id)
            .filter(Mission.creation_time >= cutoff_date)
            .distinct()
            .cte("recent_missions")
        )

        query = User.query.filter(User.creation_time < cutoff_date).filter(
            db.or_(
                User.id.notin_(users_with_active_employments),
                User.id.notin_(recent_missions),
            )
        )

        user_count = 0
        user_ids = []

        for user in query.yield_per(batch_size):
            user_ids.append(user.id)
            user_count += 1

            if len(user_ids) >= batch_size:
                logger.info(f"Processed {user_count} users so far...")
                yield user_ids
                user_ids = []

        if user_ids:
            yield user_ids

        logger.info(f"Found total of {user_count} users to anonymize")

    def process_users(self, user_ids: List[int]):
        if not user_ids:
            logger.info("No users found")
            return

        users = User.query.filter(User.id.in_(user_ids)).all()
        logger.info(f"Processing {len(users)} users...")

        for user in users:
            anonymized = UserAnonymized.anonymize(user)
            self.db.add(anonymized)

        User.query.filter(User.id.in_(user_ids)).delete(
            synchronize_session=False
        )
