from app import db
from typing import Set
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
    User,
    UserAgreement,
    RefreshToken,
    UserReadToken,
    UserSurveyActions,
    RegulatoryAlert,
    RegulationComputation,
    ControllerControl,
    ControllerUser,
    ControllerRefreshToken,
    Team,
)
from app.models.team_association_tables import (
    team_vehicle_association_table,
    team_known_address_association_table,
    team_admin_user_association_table,
)
from app.helpers.oauth import OAuth2Token, OAuth2AuthorizationCode
from app.models.anonymized import (
    AnonActivity,
    AnonActivityVersion,
    AnonMission,
    AnonMissionEnd,
    AnonMissionValidation,
    AnonLocationEntry,
    AnonEmployment,
    AnonEmail,
    AnonCompany,
    AnonCompanyCertification,
    AnonCompanyStats,
    AnonVehicle,
    AnonCompanyKnownAddress,
    AnonUserAgreement,
    AnonRegulatoryAlert,
    AnonRegulationComputation,
    AnonControllerControl,
    AnonControllerUser,
    AnonTeam,
    AnonTeamAdminUser,
    AnonTeamKnownAddress,
)
import logging

logger = logging.getLogger(__name__)


class AnonymizationExecutor:
    def __init__(self, db_session, dry_run=True):
        """
        Initialize the anonymization executor.

        This class handles the actual execution of anonymization and deletion operations
        for standalone data, creating anonymized records and/or deleting original ones.

        Args:
            db_session: SQLAlchemy database session
            dry_run: If True, no deletions will be performed (default: True)
        """
        self.db = db_session
        self.dry_run = dry_run

    def log_anonymization(
        self, count: int, entity_type: str, context: str = ""
    ):
        """
        Log information about anonymization operations.

        Args:
            count: Number of entities being processed
            entity_type: Type of entity (e.g., "mission", "company")
            context: Optional context information
        """
        if count == 0:
            logger.info(
                f"No {entity_type} found{' ' + context if context else ''}"
            )
            return

        action = "Processing"
        logger.info(
            f"{action} {count} {entity_type}{'s' if count > 1 else ''}{' ' + context if context else ''}"
        )

    def log_deletion(self, count: int, entity_type: str, context: str = ""):
        """
        Log information about deletion operations.

        Args:
            count: Number of entities being deleted
            entity_type: Type of entity (e.g., "mission", "company")
            context: Optional context information
        """
        if count > 0:
            action = "Would delete" if self.dry_run else "Deleted"
            logger.info(
                f"{action} {count} {entity_type}{'s' if count > 1 else ''}{' ' + context if context else ''}"
            )

    def get_mapped_ids(self, entity_type: str) -> Set[int]:
        """
        Get IDs that have already been mapped (anonymized).

        Args:
            entity_type: Type of entity to get mappings for (e.g., "mission", "company")

        Returns:
            Set of original IDs that have been mapped
        """
        from app.models.anonymized import IdMapping

        mappings = IdMapping.query.filter_by(entity_type=entity_type).all()
        return (
            {mapping.original_id for mapping in mappings}
            if mappings
            else set()
        )

    def anonymize_mission_and_dependencies(self, mission_ids: Set[int]):
        """
        Anonymize missions and their dependencies.
        If not in dry_run mode, will also delete the original data.

        Args:
            mission_ids: Set of mission IDs to anonymize
        """
        if not mission_ids:
            return

        self.anonymize_activities(mission_ids)
        self.anonymize_mission_ends(mission_ids)
        self.anonymize_mission_validations(mission_ids)
        self.anonymize_location_entries(mission_ids)
        self.anonymize_missions(mission_ids)

        if not self.dry_run:
            self.delete_mission_and_dependencies(mission_ids)

    def delete_mission_and_dependencies(self, mission_ids: Set[int]):
        if not mission_ids or self.dry_run:
            return

        self.delete_expenditures(mission_ids)
        self.delete_mission_comments(mission_ids)
        self.delete_activities(mission_ids)
        self.delete_mission_ends(mission_ids)
        self.delete_mission_validations(mission_ids)
        self.delete_location_entries(mission_ids)
        self.delete_missions(mission_ids)

    def anonymize_activities(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        activities = Activity.query.filter(
            Activity.mission_id.in_(mission_ids)
        ).all()

        if not activities:
            return

        activity_ids = {a.id for a in activities}
        self.anonymize_activity_versions(activity_ids)

        self.log_anonymization(len(activities), "activity")
        for activity in activities:
            anonymized = AnonActivity.anonymize(activity)
            self.db.add(anonymized)

    def delete_activities(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        activities = Activity.query.filter(
            Activity.mission_id.in_(mission_ids)
        ).all()

        if not activities:
            return

        activity_ids = {a.id for a in activities}
        self.delete_activity_versions(activity_ids)

        deleted = Activity.query.filter(Activity.id.in_(activity_ids)).delete(
            synchronize_session=False
        )
        self.log_deletion(deleted, "activity")

    def anonymize_activity_versions(self, activity_ids: Set[int]) -> None:
        if not activity_ids:
            return

        activity_versions = ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).all()

        self.log_anonymization(len(activity_versions), "activity version")
        if not activity_versions:
            return

        for version in activity_versions:
            anonymized = AnonActivityVersion.anonymize(version)
            self.db.add(anonymized)

    def delete_activity_versions(self, activity_ids: Set[int]) -> None:
        if not activity_ids:
            return

        deleted = ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "activity version")

    def anonymize_mission_ends(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        mission_ends = MissionEnd.query.filter(
            MissionEnd.mission_id.in_(mission_ids)
        ).all()

        self.log_anonymization(len(mission_ends), "mission end")
        if not mission_ends:
            return

        for mission_end in mission_ends:
            anonymized = AnonMissionEnd.anonymize(mission_end)
            self.db.add(anonymized)

    def delete_mission_ends(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        deleted = MissionEnd.query.filter(
            MissionEnd.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "mission end")

    def anonymize_mission_validations(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        validations = MissionValidation.query.filter(
            MissionValidation.mission_id.in_(mission_ids)
        ).all()

        self.log_anonymization(len(validations), "mission validation")
        if not validations:
            return

        for validation in validations:
            anonymized = AnonMissionValidation.anonymize(validation)
            self.db.add(anonymized)

    def delete_mission_validations(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        deleted = MissionValidation.query.filter(
            MissionValidation.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "mission validation")

    def anonymize_location_entries(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        entries = LocationEntry.query.filter(
            LocationEntry.mission_id.in_(mission_ids)
        ).all()

        self.log_anonymization(len(entries), "location entry")
        if not entries:
            return

        for entry in entries:
            anonymized = AnonLocationEntry.anonymize(entry)
            self.db.add(anonymized)

    def delete_location_entries(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        deleted = LocationEntry.query.filter(
            LocationEntry.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "location entry")

    def delete_expenditures(
        self, mission_ids: Set[int] = None, user_ids: Set[int] = None
    ) -> None:
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

            self.log_deletion(deleted, "expenditures")

    def delete_mission_comments(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        deleted = Comment.query.filter(
            Comment.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "comment")

    def anonymize_missions(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        missions = Mission.query.filter(Mission.id.in_(mission_ids)).all()

        self.log_anonymization(len(missions), "mission")
        if not missions:
            return

        for mission in missions:
            anonymized = AnonMission.anonymize(mission)
            self.db.add(anonymized)

    def delete_missions(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        deleted = Mission.query.filter(Mission.id.in_(mission_ids)).delete(
            synchronize_session=False
        )

        self.log_deletion(deleted, "missions")

    def anonymize_employment_and_dependencies(
        self, employment_ids: Set[int]
    ) -> None:
        """
        Anonymize employments and their dependencies.
        If not in dry_run mode, will also delete the original data.

        Args:
            employment_ids: Set of employment IDs to anonymize
        """
        if not employment_ids:
            return

        self.anonymize_emails(employment_ids=employment_ids)
        self.anonymize_employments(employment_ids)

        if not self.dry_run:
            self.delete_employment_and_dependencies(employment_ids)

    def delete_employment_and_dependencies(
        self, employment_ids: Set[int]
    ) -> None:
        if not employment_ids or self.dry_run:
            return

        self.delete_emails(employment_ids=employment_ids)
        self.delete_employments(employment_ids)

    def anonymize_emails(
        self, employment_ids: Set[int] = None, user_ids: Set[int] = None
    ) -> None:
        """brute SQL to handle legacy type not in recent email type ENUM"""
        if not employment_ids and not user_ids:
            return

        query = "SELECT * FROM email WHERE "
        conditions = []
        params = {}

        if employment_ids:
            conditions.append("employment_id = ANY(:employment_ids)")
            params["employment_ids"] = list(employment_ids)
        if user_ids:
            conditions.append("user_id = ANY(:user_ids)")
            params["user_ids"] = list(user_ids)

        query += " OR ".join(conditions)
        result = db.session.execute(query, params)
        emails = result.fetchall()

        self.log_anonymization(len(emails), "email")
        if not emails:
            return

        for email in emails:
            anonymized = AnonEmail.anonymize(email)
            self.db.add(anonymized)

    def delete_emails(
        self, employment_ids: Set[int] = None, user_ids: Set[int] = None
    ) -> None:
        if not employment_ids and not user_ids:
            return

        conditions = []
        params = {}

        if employment_ids:
            conditions.append("employment_id = ANY(:employment_ids)")
            params["employment_ids"] = list(employment_ids)
        if user_ids:
            conditions.append("user_id = ANY(:user_ids)")
            params["user_ids"] = list(user_ids)

        delete_query = "DELETE FROM email WHERE " + " OR ".join(conditions)
        result = db.session.execute(delete_query, params)

        self.log_deletion(result.rowcount, "email")

    def anonymize_employments(self, employment_ids: Set[int]) -> None:
        if not employment_ids:
            return

        employments = Employment.query.filter(
            Employment.id.in_(employment_ids)
        ).all()

        self.log_anonymization(len(employments), "employment")
        if not employments:
            return

        for employment in employments:
            anonymized = AnonEmployment.anonymize(employment)
            self.db.add(anonymized)

    def delete_employments(self, employment_ids: Set[int]) -> None:
        if not employment_ids:
            return

        deleted = Employment.query.filter(
            Employment.id.in_(employment_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "employment")

    def anonymize_company_and_dependencies(
        self, company_ids: Set[int]
    ) -> None:
        """
        Anonymize companies and their dependencies.
        If not in dry_run mode, will also delete the original data.

        Args:
            company_ids: Set of company IDs to anonymize
        """
        if not company_ids:
            return

        self.anonymize_company_team_and_dependencies(company_ids)
        self.anonymize_company_certifications(company_ids)
        self.anonymize_company_stats(company_ids)
        self.anonymize_company_vehicles(company_ids)
        self.anonymize_company_known_addresses(company_ids)
        self.anonymize_companies(company_ids)

        if not self.dry_run:
            self.delete_company_and_dependencies(company_ids)

    def delete_company_and_dependencies(self, company_ids: Set[int]) -> None:
        if not company_ids or self.dry_run:
            return

        self.delete_company_team_and_dependencies(company_ids)
        self.delete_company_certifications(company_ids)
        self.delete_company_stats(company_ids)
        self.delete_company_vehicles(company_ids)
        self.delete_company_known_addresses(company_ids)
        self.delete_companies(company_ids)

    def anonymize_companies(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        companies = Company.query.filter(Company.id.in_(company_ids)).all()

        self.log_anonymization(len(companies), "company")
        if not companies:
            return

        for company in companies:
            anonymized = AnonCompany.anonymize(company)
            self.db.add(anonymized)

    def delete_companies(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        deleted = Company.query.filter(Company.id.in_(company_ids)).delete(
            synchronize_session=False
        )

        self.log_deletion(deleted, "company")

    def anonymize_company_certifications(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        certifications = CompanyCertification.query.filter(
            CompanyCertification.company_id.in_(company_ids)
        ).all()

        self.log_anonymization(len(certifications), "company certification")
        if not certifications:
            return

        for certification in certifications:
            anonymized = AnonCompanyCertification.anonymize(certification)
            self.db.add(anonymized)

    def delete_company_certifications(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        deleted = CompanyCertification.query.filter(
            CompanyCertification.company_id.in_(company_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "company certification")

    def anonymize_company_stats(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        stats = CompanyStats.query.filter(
            CompanyStats.company_id.in_(company_ids)
        ).all()

        self.log_anonymization(len(stats), "company stat")
        if not stats:
            return

        for stat in stats:
            anonymized = AnonCompanyStats.anonymize(stat)
            self.db.add(anonymized)

    def delete_company_stats(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        deleted = CompanyStats.query.filter(
            CompanyStats.company_id.in_(company_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "company stat")

    def anonymize_company_vehicles(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        vehicles = Vehicle.query.filter(
            Vehicle.company_id.in_(company_ids)
        ).all()

        self.log_anonymization(len(vehicles), "vehicle")
        if not vehicles:
            return

        for vehicle in vehicles:
            anonymized = AnonVehicle.anonymize(vehicle)
            self.db.add(anonymized)

    def delete_company_vehicles(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        deleted = Vehicle.query.filter(
            Vehicle.company_id.in_(company_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "vehicle")

    def anonymize_company_known_addresses(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        addresses = CompanyKnownAddress.query.filter(
            CompanyKnownAddress.company_id.in_(company_ids)
        ).all()

        self.log_anonymization(len(addresses), "company known address")
        if not addresses:
            return

        for address in addresses:
            anonymized = AnonCompanyKnownAddress.anonymize(address)
            self.db.add(anonymized)

    def delete_company_known_addresses(self, company_ids: Set[int]) -> None:
        if not company_ids:
            return

        deleted = CompanyKnownAddress.query.filter(
            CompanyKnownAddress.company_id.in_(company_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "company known address")

    def anonymize_user_dependencies(self, user_ids: Set[int]) -> None:
        """
        Anonymize only user dependencies, not the users themselves.
        Users are anonymized in-place via the user_related process.
        If not in dry_run mode, will also delete the dependencies.

        Args:
            user_ids: Set of user IDs whose dependencies to anonymize
        """
        if not user_ids:
            return

        # Check if users are already anonymized
        from app.models import User
        from app.models.user import UserAccountStatus
        from app.services.anonymization.id_mapping_service import (
            IdMappingService,
        )

        users = User.query.filter(User.id.in_(user_ids)).all()
        non_anonymized = [
            u.id for u in users if u.status != UserAccountStatus.ANONYMIZED
        ]

        if non_anonymized:
            logger.warning(
                f"{len(non_anonymized)} users are not yet anonymized: {non_anonymized}. "
                "Consider anonymizing them first using the user_related process."
            )

        # For each user that needs to be anonymized, make sure they have a mapping entry
        # This ensures negative IDs are assigned consistently for already anonymized users
        for user_id in user_ids:
            IdMappingService.get_user_negative_id(user_id)

        self.anonymize_emails(user_ids=user_ids)
        self.anonymize_regulatory_alerts(user_ids)
        self.anonymize_regulation_computations(user_ids)
        self.anonymize_user_agreements(user_ids)
        self.anonymize_team_admin_users(user_ids=user_ids)
        self.anonymize_controller_controls(user_ids=user_ids)

        if not self.dry_run:
            self.delete_user_dependencies(user_ids)

    def delete_user_dependencies(self, user_ids: Set[int]) -> None:
        """
        Deletes user dependencies but not the users themselves.
        Users anonymized in-place should be preserved.

        Args:
            user_ids: Set of user IDs whose dependencies to delete
        """
        if not user_ids or self.dry_run:
            return

        self.delete_expenditures(user_ids=user_ids)
        self.delete_dismissed_company_known_address(user_ids)
        self.delete_user_oauth2_token(user_ids)
        self.delete_user_oauth2_auth_code(user_ids)
        self.delete_user_refresh_tokens(user_ids)
        self.delete_user_read_tokens(user_ids)
        self.delete_user_survey_actions(user_ids)
        self.delete_team_admin_users(user_ids=user_ids)
        self.delete_controller_controls(user_ids=user_ids)
        self.delete_emails(user_ids=user_ids)
        self.delete_regulatory_alerts(user_ids)
        self.delete_regulation_computations(user_ids)
        self.delete_user_agreements(user_ids)

    def delete_dismissed_company_known_address(
        self, user_ids: Set[int]
    ) -> None:
        if not user_ids:
            return

        deleted = CompanyKnownAddress.query.filter(
            CompanyKnownAddress.dismiss_author_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "dismissed company known address")

    def delete_user_oauth2_token(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        deleted = OAuth2Token.query.filter(
            OAuth2Token.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "Oauth2 token")

    def delete_user_oauth2_auth_code(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        deleted = OAuth2AuthorizationCode.query.filter(
            OAuth2AuthorizationCode.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "Oauth2 authorization code")

    def delete_user_refresh_tokens(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        deleted = RefreshToken.query.filter(
            RefreshToken.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "refresh token")

    def delete_user_read_tokens(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        deleted = UserReadToken.query.filter(
            UserReadToken.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "user read token")

    def delete_user_survey_actions(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        deleted = UserSurveyActions.query.filter(
            UserSurveyActions.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "user survey actions")

    def anonymize_user_vehicles(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        vehicles = Vehicle.query.filter(
            Vehicle.submitter_id.in_(user_ids)
        ).all()

        if not vehicles:
            return

        self.log_anonymization(len(vehicles), "vehicle", "for user")

        for vehicle in vehicles:
            anonymized = AnonVehicle.anonymize(vehicle)
            self.db.add(anonymized)

    def anonymize_regulatory_alerts(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id.in_(user_ids)
        ).all()

        self.log_anonymization(len(alerts), "regulatory alert")
        if not alerts:
            return

        for alert in alerts:
            anonymized = AnonRegulatoryAlert.anonymize(alert)
            self.db.add(anonymized)

    def delete_regulatory_alerts(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        deleted = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "regulatory alert")

    def anonymize_regulation_computations(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        computations = RegulationComputation.query.filter(
            RegulationComputation.user_id.in_(user_ids)
        ).all()

        self.log_anonymization(len(computations), "regulation computation")
        if not computations:
            return

        for computation in computations:
            anonymized = AnonRegulationComputation.anonymize(computation)
            self.db.add(anonymized)

    def delete_regulation_computations(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        deleted = RegulationComputation.query.filter(
            RegulationComputation.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "regulation computation")

    def anonymize_user_agreements(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        agreements = UserAgreement.query.filter(
            UserAgreement.user_id.in_(user_ids)
        ).all()

        self.log_anonymization(len(agreements), "user agreement")
        if not agreements:
            return

        for agreement in agreements:
            anonymized = AnonUserAgreement.anonymize(agreement)
            self.db.add(anonymized)

    def delete_user_agreements(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        deleted = UserAgreement.query.filter(
            UserAgreement.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "user agreement")

    def anonymize_company_team_and_dependencies(
        self, company_ids: Set[int]
    ) -> None:
        """
        Anonymize company teams and their dependencies.
        If not in dry_run mode, will also delete the original data.

        Args:
            company_ids: Set of company IDs whose teams to anonymize
        """
        if not company_ids:
            return

        employments = Employment.query.filter(
            Employment.company_id.in_(company_ids),
            Employment.team_id.isnot(None),
        ).all()

        employment_team_ids = [(e.team_id, e.user_id) for e in employments]

        for team_id, user_id in employment_team_ids:
            Employment.query.filter(
                Employment.team_id == team_id,
                Employment.user_id == user_id,
                Employment.company_id.in_(company_ids),
            ).update({Employment.team_id: None}, synchronize_session=False)

        teams = Team.query.filter(Team.company_id.in_(company_ids)).all()
        team_ids = {t.id for t in teams}

        if team_ids:
            self.anonymize_team_admin_users(team_ids=team_ids)
            self.anonymize_company_team_known_addresses(team_ids)
            self.anonymize_company_teams(team_ids)

        if not self.dry_run:
            self.delete_company_team_and_dependencies(company_ids)

    def delete_company_team_and_dependencies(
        self, company_ids: Set[int]
    ) -> None:
        if not company_ids or self.dry_run:
            return

        teams = Team.query.filter(Team.company_id.in_(company_ids)).all()
        team_ids = {t.id for t in teams}

        if team_ids:
            self.delete_team_vehicles(team_ids)
            self.delete_team_admin_users(team_ids=team_ids)
            self.delete_company_team_known_addresses(team_ids)
            self.delete_company_teams(team_ids)

    def anonymize_team_admin_users(
        self, user_ids: Set[int] = None, team_ids: Set[int] = None
    ) -> None:
        if not user_ids and not team_ids:
            return

        query = db.session.query(team_admin_user_association_table)
        if user_ids:
            relations = query.filter(
                team_admin_user_association_table.c.user_id.in_(user_ids)
            ).all()
        if team_ids:
            relations = query.filter(
                team_admin_user_association_table.c.team_id.in_(team_ids)
            ).all()

        self.log_anonymization(len(relations), "team admin user relation")
        if not relations:
            return

        for relation in relations:
            anonymized = AnonTeamAdminUser.anonymize(relation)
            self.db.add(anonymized)

    def delete_team_admin_users(
        self, user_ids: Set[int] = None, team_ids: Set[int] = None
    ) -> None:
        if not user_ids and not team_ids:
            return

        deleted = 0
        if user_ids:
            result = db.session.execute(
                team_admin_user_association_table.delete().where(
                    team_admin_user_association_table.c.user_id.in_(user_ids)
                )
            )
            deleted += result.rowcount

        if team_ids:
            result = db.session.execute(
                team_admin_user_association_table.delete().where(
                    team_admin_user_association_table.c.team_id.in_(team_ids)
                )
            )
            deleted += result.rowcount

        self.log_deletion(deleted, "team admin user relation")

    def anonymize_company_team_known_addresses(
        self, team_ids: Set[int]
    ) -> None:
        if not team_ids:
            return

        relations = (
            db.session.query(team_known_address_association_table)
            .filter(
                team_known_address_association_table.c.team_id.in_(team_ids)
            )
            .all()
        )

        self.log_anonymization(len(relations), "team known address relation")
        if not relations:
            return

        for relation in relations:
            anonymized = AnonTeamKnownAddress.anonymize(relation)
            self.db.add(anonymized)

    def delete_company_team_known_addresses(self, team_ids: Set[int]) -> None:
        if not team_ids:
            return

        result = db.session.execute(
            team_known_address_association_table.delete().where(
                team_known_address_association_table.c.team_id.in_(team_ids)
            )
        )

        self.log_deletion(result.rowcount, "team known address relation")

    def anonymize_company_teams(self, team_ids: Set[int]) -> None:
        if not team_ids:
            return

        teams = Team.query.filter(Team.id.in_(team_ids)).all()

        self.log_anonymization(len(teams), "team")
        if not teams:
            return

        for team in teams:
            anonymized = AnonTeam.anonymize(team)
            self.db.add(anonymized)

    def delete_company_teams(self, team_ids: Set[int]) -> None:
        if not team_ids:
            return

        deleted = Team.query.filter(Team.id.in_(team_ids)).delete(
            synchronize_session=False
        )

        self.log_deletion(deleted, "team")

    def delete_team_vehicles(self, team_ids: Set[int]) -> None:
        if not team_ids:
            return

        deleted = db.session.execute(
            team_vehicle_association_table.delete().where(
                team_vehicle_association_table.c.team_id.in_(team_ids)
            )
        ).rowcount

        self.log_deletion(deleted, "team vehicle association")

    def anonymize_controller_and_dependencies(
        self, controller_ids: Set[int]
    ) -> None:
        """
        Anonymize controllers and their dependencies.
        If not in dry_run mode, will also delete the original data.

        Args:
            controller_ids: Set of controller IDs to anonymize
        """
        if not controller_ids:
            return

        self.anonymize_controller_controls(controller_ids=controller_ids)
        self.anonymize_controller_user(controller_ids)

        if not self.dry_run:
            self.delete_controller_and_dependencies(controller_ids)

    def delete_controller_and_dependencies(
        self, controller_ids: Set[int]
    ) -> None:
        if not controller_ids or self.dry_run:
            return

        self.delete_controller_refresh_tokens(controller_ids)
        self.delete_controller_controls(controller_ids=controller_ids)
        self.delete_controller_user(controller_ids)

    def anonymize_controller_controls(
        self, controller_ids: Set[int] = None, user_ids: Set[int] = None
    ) -> None:
        if not controller_ids and not user_ids:
            return

        query = ControllerControl.query
        controls = []

        if controller_ids:
            controller_controls = query.filter(
                ControllerControl.controller_id.in_(controller_ids)
            ).all()
            controls.extend(controller_controls)

        if user_ids:
            user_controls = query.filter(
                ControllerControl.user_id.in_(user_ids)
            ).all()
            controls.extend(user_controls)

        self.log_anonymization(len(controls), "controller control")
        if not controls:
            return

        for control in controls:
            anonymized = AnonControllerControl.anonymize(control)
            self.db.add(anonymized)

    def delete_controller_controls(
        self, controller_ids: Set[int] = None, user_ids: Set[int] = None
    ) -> None:
        if not controller_ids and not user_ids:
            return

        query = ControllerControl.query
        deleted = 0

        if controller_ids:
            count = query.filter(
                ControllerControl.controller_id.in_(controller_ids)
            ).delete(synchronize_session=False)
            deleted += count

        if user_ids:
            count = query.filter(
                ControllerControl.user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            deleted += count

        self.log_deletion(deleted, "controller control")

    def anonymize_controller_user(self, controller_ids: Set[int]) -> None:
        if not controller_ids:
            return

        controllers = ControllerUser.query.filter(
            ControllerUser.id.in_(controller_ids)
        ).all()

        self.log_anonymization(len(controllers), "controller user")
        if not controllers:
            return

        for controller in controllers:
            anonymized = AnonControllerUser.anonymize(controller)
            self.db.add(anonymized)

    def delete_controller_user(self, controller_ids: Set[int]) -> None:
        if not controller_ids:
            return

        deleted = ControllerUser.query.filter(
            ControllerUser.id.in_(controller_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "controller user")

    def delete_controller_refresh_tokens(
        self, controller_ids: Set[int]
    ) -> None:
        if not controller_ids:
            return

        deleted = ControllerRefreshToken.query.filter(
            ControllerRefreshToken.controller_user_id.in_(controller_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "controller refresh token")
