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
    UserAnonymized,
    UserAgreementAnonymized,
    RegulatoryAlertAnonymized,
    RegulationComputationAnonymized,
    ControllerControlAnonymized,
    ControllerUserAnonymized,
    TeamAnonymized,
    TeamAdminUserAnonymized,
    TeamKnownAddressAnonymized,
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

    def anonymize_mission_and_dependencies(self, mission_ids: Set[int]):
        if not mission_ids:
            return

        self.anonymize_activities(mission_ids)
        self.anonymize_mission_ends(mission_ids)
        self.anonymize_mission_validations(mission_ids)
        self.anonymize_location_entries(mission_ids)
        self.delete_expenditures(mission_ids)
        self.delete_mission_comments(mission_ids)
        self.anonymize_missions(mission_ids)

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
            anonymized = ActivityAnonymized.anonymize(activity)
            self.db.add(anonymized)

        Activity.query.filter(Activity.id.in_(activity_ids)).delete(
            synchronize_session=False
        )

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
            anonymized = ActivityVersionAnonymized.anonymize(version)
            self.db.add(anonymized)

        ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).delete(synchronize_session=False)

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
            anonymized = MissionEndAnonymized.anonymize(mission_end)
            self.db.add(anonymized)

        MissionEnd.query.filter(MissionEnd.mission_id.in_(mission_ids)).delete(
            synchronize_session=False
        )

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
            anonymized = MissionValidationAnonymized.anonymize(validation)
            self.db.add(anonymized)

        MissionValidation.query.filter(
            MissionValidation.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

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
            anonymized = LocationEntryAnonymized.anonymize(entry)
            self.db.add(anonymized)

        LocationEntry.query.filter(
            LocationEntry.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

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

            context_str = f"for {' and '.join(context)}" if context else ""
            logger.info(
                f"Deleted {deleted} expenditures {context_str}".strip()
            )

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
            anonymized = MissionAnonymized.anonymize(mission)
            self.db.add(anonymized)

        Mission.query.filter(Mission.id.in_(mission_ids)).delete(
            synchronize_session=False
        )

    def anonymize_employment_and_dependencies(
        self, employment_ids: Set[int]
    ) -> None:
        if not employment_ids:
            return

        self.anonymize_emails(employment_ids)
        self.anonymize_employments(employment_ids)

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
            anonymized = EmailAnonymized.anonymize(email)
            self.db.add(anonymized)

        delete_query = "DELETE FROM email WHERE " + " OR ".join(conditions)
        db.session.execute(delete_query, params)

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
            anonymized = EmploymentAnonymized.anonymize(employment)
            self.db.add(anonymized)

        Employment.query.filter(Employment.id.in_(employment_ids)).delete(
            synchronize_session=False
        )

    def anonymize_company_and_dependencies(
        self, company_ids: Set[int]
    ) -> None:
        if not company_ids:
            return

        self.anonymize_company_team_and_dependencies(company_ids)
        self.anonymize_company_certifications(company_ids)
        self.anonymize_company_stats(company_ids)
        self.anonymize_company_vehicles(company_ids)
        self.anonymize_company_known_addresses(company_ids)
        self.anonymize_companies(company_ids)

    def anonymize_companies(self, company_ids: Set[int]) -> None:
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
            anonymized = CompanyCertificationAnonymized.anonymize(
                certification
            )
            self.db.add(anonymized)

        CompanyCertification.query.filter(
            CompanyCertification.company_id.in_(company_ids)
        ).delete(synchronize_session=False)

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
            anonymized = CompanyStatsAnonymized.anonymize(stat)
            self.db.add(anonymized)

        CompanyStats.query.filter(
            CompanyStats.company_id.in_(company_ids)
        ).delete(synchronize_session=False)

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
            anonymized = VehicleAnonymized.anonymize(vehicle)
            self.db.add(anonymized)

        Vehicle.query.filter(Vehicle.company_id.in_(company_ids)).delete(
            synchronize_session=False
        )

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
            anonymized = CompanyKnownAddressAnonymized.anonymize(address)
            self.db.add(anonymized)

        CompanyKnownAddress.query.filter(
            CompanyKnownAddress.company_id.in_(company_ids)
        ).delete(synchronize_session=False)

    def anonymize_user_and_dependencies(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        self.anonymize_user_vehicles(user_ids)
        self.delete_expenditures(user_ids=user_ids)
        self.delete_dismissed_company_known_address(user_ids)
        self.delete_user_oauth2_token(user_ids)
        self.delete_user_oauth2_auth_code(user_ids)
        self.delete_user_refresh_tokens(user_ids)
        self.delete_user_read_tokens(user_ids)
        self.delete_user_survey_actions(user_ids)
        self.anonymize_emails(user_ids=user_ids)
        self.anonymize_regulatory_alerts(user_ids)
        self.anonymize_regulation_computations(user_ids)
        self.anonymize_user_agreements(user_ids)
        self.anonymize_team_admin_users(user_ids=user_ids)
        self.anonymize_controller_controls(user_ids=user_ids)
        self.anonymize_users(user_ids)

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

        vehicle_ids = {v.id for v in vehicles}
        if not vehicle_ids:
            return

        Mission.query.filter(Mission.vehicle_id.in_(vehicle_ids)).update(
            {Mission.vehicle_id: None}, synchronize_session=False
        )

        self.log_anonymization(len(vehicles), "vehicle", "for user")
        for vehicle in vehicles:
            anonymized = VehicleAnonymized.anonymize(vehicle)
            self.db.add(anonymized)

        Vehicle.query.filter(Vehicle.submitter_id.in_(user_ids)).delete(
            synchronize_session=False
        )

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
            anonymized = RegulatoryAlertAnonymized.anonymize(alert)
            self.db.add(anonymized)

        RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

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
            anonymized = RegulationComputationAnonymized.anonymize(computation)
            self.db.add(anonymized)

        RegulationComputation.query.filter(
            RegulationComputation.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

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
            anonymized = UserAgreementAnonymized.anonymize(agreement)
            self.db.add(anonymized)

        UserAgreement.query.filter(UserAgreement.user_id.in_(user_ids)).delete(
            synchronize_session=False
        )

    def anonymize_users(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        users = User.query.filter(User.id.in_(user_ids)).all()

        self.log_anonymization(len(users), "user")
        if not users:
            return

        for user in users:
            anonymized = UserAnonymized.anonymize(user)
            self.db.add(anonymized)

        User.query.filter(User.id.in_(user_ids)).delete(
            synchronize_session=False
        )

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
            anonymized = TeamAdminUserAnonymized.anonymize(relation)
            self.db.add(anonymized)

        if user_ids:
            db.session.execute(
                team_admin_user_association_table.delete().where(
                    team_admin_user_association_table.c.user_id.in_(user_ids)
                )
            )
        if team_ids:
            db.session.execute(
                team_admin_user_association_table.delete().where(
                    team_admin_user_association_table.c.team_id.in_(team_ids)
                )
            )

    def anonymize_company_team_and_dependencies(
        self, company_ids: Set[int]
    ) -> None:
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
            self.delete_team_vehicles(team_ids)
            self.anonymize_company_teams(team_ids)

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
            anonymized = TeamKnownAddressAnonymized.anonymize(relation)
            self.db.add(anonymized)

        db.session.execute(
            team_known_address_association_table.delete().where(
                team_known_address_association_table.c.team_id.in_(team_ids)
            )
        )

    def anonymize_company_teams(self, team_ids: Set[int]) -> None:
        if not team_ids:
            return

        teams = Team.query.filter(Team.id.in_(team_ids)).all()

        self.log_anonymization(len(teams), "team")
        if not teams:
            return

        for team in teams:
            anonymized = TeamAnonymized.anonymize(team)
            self.db.add(anonymized)

        Team.query.filter(Team.id.in_(team_ids)).delete(
            synchronize_session=False
        )

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
        if not controller_ids:
            return

        self.delete_controller_refresh_tokens(controller_ids)
        self.anonymize_controller_controls(controller_ids=controller_ids)
        self.anonymize_controller_user(controller_ids)

    def delete_controller_refresh_tokens(
        self, controller_ids: Set[int]
    ) -> None:
        if not controller_ids:
            return

        deleted = ControllerRefreshToken.query.filter(
            ControllerRefreshToken.controller_user_id.in_(controller_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "controller refresh token")

    def anonymize_controller_controls(
        self, controller_ids: Set[int] = None, user_ids: Set[int] = None
    ) -> None:
        if not controller_ids and not user_ids:
            return

        query = ControllerControl.query
        if controller_ids:
            controls = query.filter(
                ControllerControl.controller_id.in_(controller_ids)
            ).all()
        if user_ids:
            controls = query.filter(
                ControllerControl.user_id.in_(user_ids)
            ).all()

        self.log_anonymization(len(controls), "controller control")
        if not controls:
            return

        for control in controls:
            anonymized = ControllerControlAnonymized.anonymize(control)
            self.db.add(anonymized)

        if controller_ids:
            query.filter(
                ControllerControl.controller_id.in_(controller_ids)
            ).delete(synchronize_session=False)
        if user_ids:
            query.filter(ControllerControl.user_id.in_(user_ids)).delete(
                synchronize_session=False
            )

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
            anonymized = ControllerUserAnonymized.anonymize(controller)
            self.db.add(anonymized)

        ControllerUser.query.filter(
            ControllerUser.id.in_(controller_ids)
        ).delete(synchronize_session=False)
