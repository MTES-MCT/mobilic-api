from app import db
from typing import Set, Dict
from app.models import (
    Activity,
    ActivityVersion,
    Mission,
    MissionEnd,
    MissionValidation,
    MissionAutoValidation,
    LocationEntry,
    Expenditure,
    Comment,
    Employment,
    Company,
    CompanyCertification,
    CompanyStats,
    Vehicle,
    CompanyKnownAddress,
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
from app.helpers.oauth.models import (
    ThirdPartyClientEmployment,
    ThirdPartyClientCompany,
)
from app.models.user import UserAccountStatus
from app.models.team_association_tables import (
    team_vehicle_association_table,
    team_known_address_association_table,
    team_admin_user_association_table,
)
from app.helpers.oauth import OAuth2Token, OAuth2AuthorizationCode
from app.models.anonymized import (
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
from app.services.anonymization.id_mapping_service import IdMappingService
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Human-readable entity labels reused across the anonymize/log/delete calls
LABEL_ACTIVITY_VERSION = "activity version"
LABEL_MISSION_END = "mission end"
LABEL_MISSION_VALIDATION = "mission validation"
LABEL_LOCATION_ENTRY = "location entry"

# Single source for the columns of the set-based INSERT...SELECT queries
# below. Adding a column to an anon_* model requires updating the matching
# tuple here AND the SELECT expressions (kept in the same order) of the
# corresponding query. test_anonymization_set_based fails on any drift
# between these tuples and the ORM models.
ANON_TABLE_COLUMNS = {
    "anon_activity": (
        "id",
        "type",
        "user_id",
        "submitter_id",
        "mission_id",
        "creation_time",
        "start_time",
        "end_time",
        "last_update_time",
    ),
    "anon_activity_version": (
        "id",
        "creation_time",
        "activity_id",
        "start_time",
        "end_time",
        "version_number",
        "submitter_id",
    ),
    "anon_mission_end": (
        "id",
        "creation_time",
        "mission_id",
        "user_id",
        "submitter_id",
    ),
    "anon_mission_validation": (
        "id",
        "creation_time",
        "mission_id",
        "submitter_id",
        "user_id",
        "is_admin",
    ),
    "anon_location_entry": (
        "id",
        "submitter_id",
        "type",
        "creation_time",
        "mission_id",
        "address_id",
        "company_known_address_id",
    ),
    "anon_mission": ("id", "creation_time", "submitter_id", "company_id"),
}


def anon_insert_clause(table: str) -> str:
    return f"INSERT INTO {table} ({', '.join(ANON_TABLE_COLUMNS[table])})"


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

    def count_rows(self, count_sql: str, mission_ids: Set[int]) -> int:
        return self.db.execute(
            text(count_sql), {"mids": list(mission_ids)}
        ).scalar()

    def log_copy_reconciliation(
        self, entity_type: str, source_count: int, inserted_count: int
    ) -> None:
        skipped = source_count - inserted_count
        if skipped > 0:
            logger.warning(
                f"{skipped}/{source_count} {entity_type} source rows were "
                "not copied to the anonymized table (missing id mapping, "
                "NULL FK on a strict JOIN, or already copied by a "
                "previous run)"
            )

    def anonymize_mission_and_dependencies(self, mission_ids: Set[int]):
        """
        Anonymize missions and their dependencies.
        Marks missions as deletion targets during anonymization.
        If not in dry_run mode, will also delete the original data.

        Args:
            mission_ids: Set of mission IDs to anonymize
        """
        if not mission_ids:
            return

        IdMappingService.mark_all_for_deletion("mission", mission_ids)
        IdMappingService.seed_mission_subtree_mappings(mission_ids)

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
        self.delete_mission_auto_validations(mission_ids)
        self.delete_location_entries(mission_ids)
        self.delete_missions(mission_ids)

    def anonymize_activities(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        self.anonymize_activity_versions(mission_ids)

        source_count = self.count_rows(
            "SELECT count(*) FROM activity WHERE mission_id = ANY(:mids)",
            mission_ids,
        )
        result = self.db.execute(
            text(
                f"""
                {anon_insert_clause("anon_activity")}
                SELECT ma.anonymized_id, a.type, mu.anonymized_id,
                       ms.anonymized_id, mm.anonymized_id,
                       date_trunc('month', a.creation_time),
                       date_trunc('month', a.start_time),
                       CASE WHEN a.end_time IS NOT NULL THEN
                           date_trunc('month', a.start_time)
                           + (a.end_time - a.start_time)
                       END,
                       date_trunc('month', a.last_update_time)
                FROM activity a
                JOIN temp_id_mapping ma ON ma.entity_type = 'activity'
                    AND ma.original_id = a.id
                JOIN temp_id_mapping mm ON mm.entity_type = 'mission'
                    AND mm.original_id = a.mission_id
                JOIN temp_id_mapping mu ON mu.entity_type = 'user'
                    AND mu.original_id = a.user_id
                JOIN temp_id_mapping ms ON ms.entity_type = 'user'
                    AND ms.original_id = a.submitter_id
                WHERE a.mission_id = ANY(:mids)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mids": list(mission_ids)},
        )
        self.log_anonymization(result.rowcount, "activity")
        self.log_copy_reconciliation("activity", source_count, result.rowcount)

    def delete_activities(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        activity_ids = {
            row[0]
            for row in Activity.query.filter(
                Activity.mission_id.in_(mission_ids)
            ).with_entities(Activity.id)
        }

        if not activity_ids:
            return

        self.delete_activity_versions(activity_ids)

        deleted = Activity.query.filter(Activity.id.in_(activity_ids)).delete(
            synchronize_session=False
        )
        self.log_deletion(deleted, "activity")

    def anonymize_activity_versions(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        source_count = self.count_rows(
            "SELECT count(*) FROM activity_version av "
            "JOIN activity a ON a.id = av.activity_id "
            "WHERE a.mission_id = ANY(:mids)",
            mission_ids,
        )
        result = self.db.execute(
            text(
                f"""
                {anon_insert_clause("anon_activity_version")}
                SELECT mav.anonymized_id,
                       date_trunc('month', av.creation_time),
                       ma.anonymized_id,
                       date_trunc('month', av.start_time),
                       CASE WHEN av.end_time IS NOT NULL THEN
                           date_trunc('month', av.start_time)
                           + (av.end_time - av.start_time)
                       END,
                       av.version_number, ms.anonymized_id
                FROM activity_version av
                JOIN activity a ON a.id = av.activity_id
                JOIN temp_id_mapping mav
                    ON mav.entity_type = 'activity_version'
                    AND mav.original_id = av.id
                JOIN temp_id_mapping ma ON ma.entity_type = 'activity'
                    AND ma.original_id = av.activity_id
                JOIN temp_id_mapping ms ON ms.entity_type = 'user'
                    AND ms.original_id = av.submitter_id
                WHERE a.mission_id = ANY(:mids)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mids": list(mission_ids)},
        )
        self.log_anonymization(result.rowcount, LABEL_ACTIVITY_VERSION)
        self.log_copy_reconciliation(
            LABEL_ACTIVITY_VERSION, source_count, result.rowcount
        )

    def delete_activity_versions(self, activity_ids: Set[int]) -> None:
        if not activity_ids:
            return

        deleted = ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, LABEL_ACTIVITY_VERSION)

    def anonymize_mission_ends(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        self.warn_skipped_null_submitters("mission_end", mission_ids)

        source_count = self.count_rows(
            "SELECT count(*) FROM mission_end WHERE mission_id = ANY(:mids)",
            mission_ids,
        )
        result = self.db.execute(
            text(
                f"""
                {anon_insert_clause("anon_mission_end")}
                SELECT mme.anonymized_id,
                       date_trunc('month', me.creation_time),
                       mm.anonymized_id, mu.anonymized_id, ms.anonymized_id
                FROM mission_end me
                JOIN temp_id_mapping mme ON mme.entity_type = 'mission_end'
                    AND mme.original_id = me.id
                JOIN temp_id_mapping mm ON mm.entity_type = 'mission'
                    AND mm.original_id = me.mission_id
                JOIN temp_id_mapping mu ON mu.entity_type = 'user'
                    AND mu.original_id = me.user_id
                JOIN temp_id_mapping ms ON ms.entity_type = 'user'
                    AND ms.original_id = me.submitter_id
                WHERE me.mission_id = ANY(:mids)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mids": list(mission_ids)},
        )
        self.log_anonymization(result.rowcount, LABEL_MISSION_END)
        self.log_copy_reconciliation(
            LABEL_MISSION_END, source_count, result.rowcount
        )

    def delete_mission_ends(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        deleted = MissionEnd.query.filter(
            MissionEnd.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, LABEL_MISSION_END)

    def anonymize_mission_validations(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        self.warn_skipped_null_submitters("mission_validation", mission_ids)

        source_count = self.count_rows(
            "SELECT count(*) FROM mission_validation "
            "WHERE mission_id = ANY(:mids)",
            mission_ids,
        )
        result = self.db.execute(
            text(
                f"""
                {anon_insert_clause("anon_mission_validation")}
                SELECT mmv.anonymized_id,
                       date_trunc('month', v.creation_time),
                       mm.anonymized_id, ms.anonymized_id, mu.anonymized_id,
                       v.is_admin
                FROM mission_validation v
                JOIN temp_id_mapping mmv
                    ON mmv.entity_type = 'mission_validation'
                    AND mmv.original_id = v.id
                JOIN temp_id_mapping mm ON mm.entity_type = 'mission'
                    AND mm.original_id = v.mission_id
                JOIN temp_id_mapping ms ON ms.entity_type = 'user'
                    AND ms.original_id = v.submitter_id
                LEFT JOIN temp_id_mapping mu ON mu.entity_type = 'user'
                    AND mu.original_id = v.user_id
                WHERE v.mission_id = ANY(:mids)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mids": list(mission_ids)},
        )
        self.log_anonymization(result.rowcount, LABEL_MISSION_VALIDATION)
        self.log_copy_reconciliation(
            LABEL_MISSION_VALIDATION, source_count, result.rowcount
        )

    def delete_mission_validations(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        deleted = MissionValidation.query.filter(
            MissionValidation.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, LABEL_MISSION_VALIDATION)

    def delete_mission_auto_validations(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        deleted = MissionAutoValidation.query.filter(
            MissionAutoValidation.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "mission auto validation")

    def anonymize_location_entries(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        source_count = self.count_rows(
            "SELECT count(*) FROM location_entry "
            "WHERE mission_id = ANY(:mids)",
            mission_ids,
        )
        result = self.db.execute(
            text(
                f"""
                {anon_insert_clause("anon_location_entry")}
                SELECT mle.anonymized_id, ms.anonymized_id, le.type,
                       date_trunc('month', le.creation_time),
                       mm.anonymized_id, mad.anonymized_id,
                       mcka.anonymized_id
                FROM location_entry le
                JOIN temp_id_mapping mle
                    ON mle.entity_type = 'location_entry'
                    AND mle.original_id = le.id
                JOIN temp_id_mapping mm ON mm.entity_type = 'mission'
                    AND mm.original_id = le.mission_id
                JOIN temp_id_mapping ms ON ms.entity_type = 'user'
                    AND ms.original_id = le.submitter_id
                JOIN temp_id_mapping mad ON mad.entity_type = 'address'
                    AND mad.original_id = le.address_id
                LEFT JOIN temp_id_mapping mcka
                    ON mcka.entity_type = 'company_known_address'
                    AND mcka.original_id = le.company_known_address_id
                WHERE le.mission_id = ANY(:mids)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mids": list(mission_ids)},
        )
        self.log_anonymization(result.rowcount, LABEL_LOCATION_ENTRY)
        self.log_copy_reconciliation(
            LABEL_LOCATION_ENTRY, source_count, result.rowcount
        )

    def delete_location_entries(self, mission_ids: Set[int]) -> None:
        if not mission_ids:
            return

        deleted = LocationEntry.query.filter(
            LocationEntry.mission_id.in_(mission_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, LABEL_LOCATION_ENTRY)

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

        source_count = self.count_rows(
            "SELECT count(*) FROM mission WHERE id = ANY(:mids)",
            mission_ids,
        )
        result = self.db.execute(
            text(
                f"""
                {anon_insert_clause("anon_mission")}
                SELECT mm.anonymized_id,
                       date_trunc('month', m.creation_time),
                       ms.anonymized_id, mc.anonymized_id
                FROM mission m
                JOIN temp_id_mapping mm ON mm.entity_type = 'mission'
                    AND mm.original_id = m.id
                JOIN temp_id_mapping ms ON ms.entity_type = 'user'
                    AND ms.original_id = m.submitter_id
                JOIN temp_id_mapping mc ON mc.entity_type = 'company'
                    AND mc.original_id = m.company_id
                WHERE m.id = ANY(:mids)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mids": list(mission_ids)},
        )
        self.log_anonymization(result.rowcount, "mission")
        self.log_copy_reconciliation("mission", source_count, result.rowcount)

    def warn_skipped_null_submitters(
        self, table: str, mission_ids: Set[int]
    ) -> None:
        """Count source rows whose NULL submitter cannot fit the NOT NULL
        anon column: the strict JOIN of the set-based copy skips them."""
        if table not in ("mission_end", "mission_validation"):
            raise ValueError(
                f"Unexpected table for null-submitter check: {table}"
            )
        skipped = self.db.execute(
            text(
                f"SELECT count(*) FROM {table} "
                "WHERE mission_id = ANY(:mids) AND submitter_id IS NULL"
            ),
            {"mids": list(mission_ids)},
        ).scalar()
        if skipped:
            logger.warning(
                f"{skipped} {table} rows have a NULL submitter and were "
                "not copied to the anonymized table"
            )

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
        Marks employments as deletion targets during anonymization.
        If not in dry_run mode, will also delete the original data.

        Args:
            employment_ids: Set of employment IDs to anonymize
        """
        if not employment_ids:
            return

        IdMappingService.mark_all_for_deletion("employment", employment_ids)

        self.anonymize_emails(employment_ids=employment_ids)
        self.anonymize_employments(employment_ids)

        if not self.dry_run:
            self.delete_employment_and_dependencies(employment_ids)

    def delete_employment_and_dependencies(
        self, employment_ids: Set[int]
    ) -> None:
        if not employment_ids or self.dry_run:
            return

        self.delete_third_party_client_employment(employment_ids)
        self.delete_emails(employment_ids=employment_ids)
        self.delete_employments(employment_ids)

    def delete_third_party_client_employment(
        self, employment_ids: Set[int]
    ) -> None:
        if not employment_ids:
            return

        deleted = ThirdPartyClientEmployment.query.filter(
            ThirdPartyClientEmployment.employment_id.in_(employment_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "third party client employment")

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

        mappings = IdMappingService.prefetch_mappings(
            "email", {e.id for e in emails}
        )
        IdMappingService.prefetch_mappings("user", {e.user_id for e in emails})
        IdMappingService.prefetch_mappings(
            "employment", {e.employment_id for e in emails}
        )
        AnonEmail.prime_existing_records(mappings.values())
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

        mappings = IdMappingService.prefetch_mappings(
            "employment", {e.id for e in employments}
        )
        IdMappingService.prefetch_mappings(
            "company", {e.company_id for e in employments}
        )
        IdMappingService.prefetch_mappings(
            "user",
            {e.user_id for e in employments}
            | {e.submitter_id for e in employments},
        )
        IdMappingService.prefetch_mappings(
            "team", {e.team_id for e in employments}
        )
        IdMappingService.prefetch_mappings(
            "business", {e.business_id for e in employments}
        )
        AnonEmployment.prime_existing_records(mappings.values())
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
        Marks companies as deletion targets during anonymization.
        If not in dry_run mode, will also delete the original data.

        Args:
            company_ids: Set of company IDs to anonymize
        """
        if not company_ids:
            return

        IdMappingService.mark_all_for_deletion("company", company_ids)

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

        if not vehicles:
            return

        self.log_anonymization(len(vehicles), "vehicle")

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

        logger.info(f"Anonymizing dependencies for {len(user_ids)} users")

        IdMappingService.mark_all_for_deletion("user", user_ids)

        self.anonymize_user_employments(user_ids)
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
        After deleting dependencies, updates user IDs to their negative values.

        Args:
            user_ids: Set of user IDs whose dependencies to delete
        """
        if not user_ids or self.dry_run:
            return

        self.delete_dismissed_and_user_employments(user_ids)
        self.delete_expenditures(user_ids=user_ids)
        self.delete_dismissed_third_party_client_company(user_ids)
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

        self.update_anonymized_users_with_negative_ids(user_ids)

    def delete_dismissed_third_party_client_company(
        self, user_ids: Set[int]
    ) -> None:
        if not user_ids:
            return

        deleted = ThirdPartyClientCompany.query.filter(
            ThirdPartyClientCompany.dismiss_author_id.in_(user_ids)
        ).delete(synchronize_session=False)

        self.log_deletion(deleted, "dismissed third party client company")

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

    def anonymize_regulatory_alerts(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id.in_(user_ids)
        ).all()

        self.log_anonymization(len(alerts), "regulatory alert")
        if not alerts:
            return

        mappings = IdMappingService.prefetch_mappings(
            "regulatory_alert", {a.id for a in alerts}
        )
        IdMappingService.prefetch_mappings("user", {a.user_id for a in alerts})
        AnonRegulatoryAlert.prime_existing_records(mappings.values())
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

        mappings = IdMappingService.prefetch_mappings(
            "regulation_computation", {c.id for c in computations}
        )
        IdMappingService.prefetch_mappings(
            "user", {c.user_id for c in computations}
        )
        AnonRegulationComputation.prime_existing_records(mappings.values())
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

        mappings = IdMappingService.prefetch_mappings(
            "user_agreement", {a.id for a in agreements}
        )
        IdMappingService.prefetch_mappings(
            "user", {a.user_id for a in agreements}
        )
        AnonUserAgreement.prime_existing_records(mappings.values())
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

    def anonymize_user_employments(self, user_ids: Set[int]) -> None:
        if not user_ids:
            return

        employment_ids = set(
            id
            for (id,) in Employment.query.filter(
                Employment.user_id.in_(user_ids)
            )
            .with_entities(Employment.id)
            .all()
        )

        dismiss_author_employment_ids = set(
            id
            for (id,) in Employment.query.filter(
                Employment.dismiss_author_id.in_(user_ids)
            )
            .with_entities(Employment.id)
            .all()
        )

        employment_ids.update(dismiss_author_employment_ids)

        if employment_ids:
            self.anonymize_employment_and_dependencies(employment_ids)

    def delete_dismissed_and_user_employments(
        self, user_ids: Set[int]
    ) -> None:
        if not user_ids:
            return

        employment_ids = set(
            id
            for (id,) in Employment.query.filter(
                Employment.user_id.in_(user_ids)
            )
            .with_entities(Employment.id)
            .all()
        )

        dismiss_author_employment_ids = set(
            id
            for (id,) in Employment.query.filter(
                Employment.dismiss_author_id.in_(user_ids)
            )
            .with_entities(Employment.id)
            .all()
        )

        employment_ids.update(dismiss_author_employment_ids)

        if employment_ids:
            self.delete_employment_and_dependencies(employment_ids)

    def update_anonymized_users_with_negative_ids(
        self, user_ids: Set[int]
    ) -> None:
        """
        Updates anonymized users with positive IDs to use their negative ID mappings.
        If any update fails, the entire process is interrupted.

        Args:
            user_ids: Optional set of user IDs to update. If None, will update all users
                     marked as deletion targets in the ID mapping table
        """
        if not user_ids:
            return

        IdMappingService.prefetch_mappings("user", user_ids)
        for user_id in user_ids:
            negative_id = IdMappingService.get_user_negative_id(user_id)

            self.db.execute(
                text(
                    'UPDATE "user" SET id = :new_id, email = :new_email WHERE id = :old_id'
                ),
                {
                    "new_id": negative_id,
                    "old_id": user_id,
                    "new_email": f"anon_{negative_id}@anonymous.aa",
                },
            )

        logger.info(f"Updated {len(user_ids)} users to negative IDs")

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

        IdMappingService.mark_all_for_deletion("controller", controller_ids)

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

        mappings = IdMappingService.prefetch_mappings(
            "controller_control", {c.id for c in controls}
        )
        # controller_id is mapped through the "user" entity type
        IdMappingService.prefetch_mappings(
            "user",
            {c.controller_id for c in controls}
            | {c.user_id for c in controls},
        )
        AnonControllerControl.prime_existing_records(mappings.values())
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
