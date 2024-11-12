from app import db
from typing import List
from app.models import (
    Activity,
    ActivityVersion,
    Mission,
    MissionEnd,
    MissionValidation,
    LocationEntry,
    Expenditure,
    Comment,
    Employment,
    Company,
    CompanyCertification,
    CompanyStats,
    Vehicle,
    CompanyKnownAddress,
)
from app.models.anonymized import (
    ActivityAnonymized,
    ActivityVersionAnonymized,
    MissionAnonymized,
    MissionEndAnonymized,
    MissionValidationAnonymized,
    LocationEntryAnonymized,
    EmploymentAnonymized,
    EmailAnonymized,
    CompanyAnonymized,
    CompanyCertificationAnonymized,
    CompanyStatsAnonymized,
    VehicleAnonymized,
    CompanyKnownAddressAnonymized,
)
import logging

logger = logging.getLogger(__name__)


class BaseAnonymizer:
    def __init__(self, db_session):
        self.db = db_session

    def log_anonymization(
        self, count: int, entity_type: str, context: str = ""
    ):
        if count == 0:
            logger.info(
                f"No {entity_type} found{' ' + context if context else ''}"
            )
            return
        logger.info(
            f"Processing {count} {entity_type}{'s' if count > 1 else ''}{' ' + context if context else ''}"
        )

    def log_deletion(self, count: int, entity_type: str, context: str = ""):
        if count > 0:
            logger.info(
                f"Deleted {count} {entity_type}{'s' if count > 1 else ''}{' ' + context if context else ''}"
            )

    def anonymize_mission_and_dependencies(self, mission_ids: List[int]):
        if not mission_ids:
            return

        self.anonymize_activities(mission_ids)
        self.anonymize_mission_ends(mission_ids)
        self.anonymize_mission_validations(mission_ids)
        self.anonymize_location_entries(mission_ids)
        self.delete_expenditures(mission_ids)
        self.delete_mission_comments(mission_ids)
        self.anonymize_missions(mission_ids)

    def anonymize_activities(self, mission_ids: List[int]) -> List[int]:
        if not mission_ids:
            return []

        activities = Activity.query.filter(
            Activity.mission_id.in_(mission_ids)
        ).all()

        if not activities:
            return []

        activity_ids = [a.id for a in activities]
        self.anonymize_activity_versions(activity_ids)

        self.log_anonymization(len(activities), "activity")
        for activity in activities:
            anonymized = ActivityAnonymized.anonymize(activity)
            self.db.add(anonymized)

        Activity.query.filter(Activity.id.in_(activity_ids)).delete(
            synchronize_session=False
        )
        return activity_ids

    def anonymize_activity_versions(self, activity_ids: List[int]) -> int:
        activity_versions = ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).all()

        if not activity_versions:
            return 0

        self.log_anonymization(len(activity_versions), "activity version")
        for version in activity_versions:
            anonymized = ActivityVersionAnonymized.anonymize(version)
            self.db.add(anonymized)

        ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).delete(synchronize_session=False)

        return len(activity_versions)

    def anonymize_mission_ends(self, mission_ids: List[int]):
        if not mission_ids:
            return

        mission_ends = MissionEnd.query.filter(
            MissionEnd.mission_id.in_(mission_ids)
        ).all()

        self.log_anonymization(len(mission_ends), "mission end")
        if not mission_ends:
            return

        for mission_end in mission_ends:
            anonymized = MissionEndAnonymized.anonymize(mission_end)
            self.db.add(anonymized)

        MissionEnd.query.filter(MissionEnd.mission_id.in_(mission_ids)).delete(
            synchronize_session=False
        )

    def anonymize_mission_validations(self, mission_ids: List[int]):
        if not mission_ids:
            return

        validations = MissionValidation.query.filter(
            MissionValidation.mission_id.in_(mission_ids)
        ).all()

        self.log_anonymization(len(validations), "mission validation")
        if not validations:
            return

        for validation in validations:
            anonymized = MissionValidationAnonymized.anonymize(validation)
            self.db.add(anonymized)

        MissionValidation.query.filter(
            MissionValidation.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

    def anonymize_location_entries(self, mission_ids: List[int]):
        if not mission_ids:
            return

        entries = LocationEntry.query.filter(
            LocationEntry.mission_id.in_(mission_ids)
        ).all()

        self.log_anonymization(len(entries), "location entry")
        if not entries:
            return

        for entry in entries:
            anonymized = LocationEntryAnonymized.anonymize(entry)
            self.db.add(anonymized)

        LocationEntry.query.filter(
            LocationEntry.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

    def delete_expenditures(
        self, mission_ids: List[int] = None, user_ids: List[int] = None
    ):
        if not mission_ids and not user_ids:
            return

        query = Expenditure.query
        filters = []
        if mission_ids:
            filters.append(Expenditure.mission_id.in_(mission_ids))
        if user_ids:
            filters.append(Expenditure.user_id.in_(user_ids))

        deleted = query.filter(db.or_(*filters)).delete(
            synchronize_session=False
        )
        if deleted:
            context = []
            if mission_ids:
                context.append("missions")
            if user_ids:
                context.append("users")

            context_str = f"for {' and '.join(context)}" if context else ""
            logger.info(
                f"Deleted {deleted} expenditures {context_str}".strip()
            )

    def delete_mission_comments(self, mission_ids: List[int]):
        if not mission_ids:
            return

        deleted = Comment.query.filter(
            Comment.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "comment")

    def anonymize_missions(self, mission_ids: List[int]):
        if not mission_ids:
            return

        missions = Mission.query.filter(Mission.id.in_(mission_ids)).all()

        self.log_anonymization(len(missions), "mission")
        if not missions:
            return

        for mission in missions:
            anonymized = MissionAnonymized.anonymize(mission)
            self.db.add(anonymized)

        Mission.query.filter(Mission.id.in_(mission_ids)).delete(
            synchronize_session=False
        )

    def anonymize_employment_and_dependencies(self, employment_ids: List[int]):
        if not employment_ids:
            return

        self.anonymize_emails(employment_ids)
        self.anonymize_employments(employment_ids)

    def anonymize_emails(
        self, employment_ids: List[int] = None, user_ids: List[int] = None
    ):
        """brute SQL to handle legacy type not in recent email type ENUM"""
        if not employment_ids and not user_ids:
            return

        query = "SELECT * FROM email WHERE "
        conditions = []
        params = {}

        if employment_ids:
            conditions.append("employment_id = ANY(:employment_ids)")
            params["employment_ids"] = employment_ids
        if user_ids:
            conditions.append("user_id = ANY(:user_ids)")
            params["user_ids"] = user_ids

        query += " OR ".join(conditions)
        result = db.session.execute(query, params)
        emails = result.fetchall()

        self.log_anonymization(len(emails), "email")
        if not emails:
            return

        for email in emails:
            anonymized = EmailAnonymized.anonymize(email)
            self.db.add(anonymized)

        delete_query = "DELETE FROM email WHERE " + " OR ".join(conditions)
        db.session.execute(delete_query, params)

    def anonymize_employments(self, employment_ids: List[int]):
        if not employment_ids:
            return

        employments = Employment.query.filter(
            Employment.id.in_(employment_ids)
        ).all()

        self.log_anonymization(len(employments), "employment")
        if not employments:
            return

        for employment in employments:
            anonymized = EmploymentAnonymized.anonymize(employment)
            self.db.add(anonymized)

        Employment.query.filter(Employment.id.in_(employment_ids)).delete(
            synchronize_session=False
        )

    def anonymize_company_and_dependencies(self, company_ids: List[int]):
        if not company_ids:
            return

        self.anonymize_company_certifications(company_ids)
        self.anonymize_company_stats(company_ids)
        self.anonymize_company_vehicles(company_ids)
        self.anonymize_company_known_addresses(company_ids)
        self.anonymize_companies(company_ids)

    def anonymize_companies(self, company_ids: List[int]):
        if not company_ids:
            return

        companies = Company.query.filter(Company.id.in_(company_ids)).all()

        self.log_anonymization(len(companies), "company")
        if not companies:
            return

        for company in companies:
            anonymized = CompanyAnonymized.anonymize(company)
            self.db.add(anonymized)

        Company.query.filter(Company.id.in_(company_ids)).delete(
            synchronize_session=False
        )

    def anonymize_company_certifications(self, company_ids: List[int]):
        if not company_ids:
            return

        certifications = CompanyCertification.query.filter(
            CompanyCertification.company_id.in_(company_ids)
        ).all()

        self.log_anonymization(len(certifications), "company certification")
        if not certifications:
            return

        for certification in certifications:
            anonymized = CompanyCertificationAnonymized.anonymize(
                certification
            )
            self.db.add(anonymized)

        CompanyCertification.query.filter(
            CompanyCertification.company_id.in_(company_ids)
        ).delete(synchronize_session=False)

    def anonymize_company_stats(self, company_ids: List[int]):
        if not company_ids:
            return

        stats = CompanyStats.query.filter(
            CompanyStats.company_id.in_(company_ids)
        ).all()

        self.log_anonymization(len(stats), "company stat")
        if not stats:
            return

        for stat in stats:
            anonymized = CompanyStatsAnonymized.anonymize(stat)
            self.db.add(anonymized)

        CompanyStats.query.filter(
            CompanyStats.company_id.in_(company_ids)
        ).delete(synchronize_session=False)

    def anonymize_company_vehicles(self, company_ids: List[int]):
        if not company_ids:
            return

        vehicles = Vehicle.query.filter(
            Vehicle.company_id.in_(company_ids)
        ).all()

        self.log_anonymization(len(vehicles), "vehicle")
        if not vehicles:
            return

        for vehicle in vehicles:
            anonymized = VehicleAnonymized.anonymize(vehicle)
            self.db.add(anonymized)

        Vehicle.query.filter(Vehicle.company_id.in_(company_ids)).delete(
            synchronize_session=False
        )

    def anonymize_company_known_addresses(self, company_ids: List[int]):
        if not company_ids:
            return

        addresses = CompanyKnownAddress.query.filter(
            CompanyKnownAddress.company_id.in_(company_ids)
        ).all()

        self.log_anonymization(len(addresses), "company known address")
        if not addresses:
            return

        for address in addresses:
            anonymized = CompanyKnownAddressAnonymized.anonymize(address)
            self.db.add(anonymized)

        CompanyKnownAddress.query.filter(
            CompanyKnownAddress.company_id.in_(company_ids)
        ).delete(synchronize_session=False)
