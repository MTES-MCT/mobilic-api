from app import db
from typing import List, Dict, Set, Tuple
from datetime import datetime
import logging
import time

from app.models import (
    Mission,
    MissionEnd,
    MissionValidation,
    Employment,
    Expenditure,
    Comment,
)

from app.services.anonymization.standalone import StandaloneAnonymizer

logger = logging.getLogger(__name__)


class UserRelatedTableInfo:
    def __init__(self, table_name: str, user_columns: List[str]):
        self.table_name = table_name
        self.user_columns = user_columns


class UserClassifier:
    def __init__(self, cutoff_date: datetime):
        self.cutoff_date = cutoff_date
        self.user_related_tables = self._init_user_related_tables()
        self.dismissable_tables = self._init_dismissable_tables()
        self.anonymizer = StandaloneAnonymizer(db.session)

    def _init_user_related_tables(self) -> List[UserRelatedTableInfo]:
        return [
            UserRelatedTableInfo("mission", ["submitter_id"]),
            UserRelatedTableInfo("mission_end", ["user_id", "submitter_id"]),
            UserRelatedTableInfo(
                "mission_validation", ["submitter_id", "user_id"]
            ),
            UserRelatedTableInfo(
                "employment", ["user_id", "submitter_id", "dismiss_author_id"]
            ),
            UserRelatedTableInfo(
                "expenditure", ["user_id", "submitter_id", "dismiss_author_id"]
            ),
            UserRelatedTableInfo(
                "comment", ["submitter_id", "dismiss_author_id"]
            ),
            UserRelatedTableInfo(
                "activity", ["user_id", "submitter_id", "dismiss_author_id"]
            ),
            UserRelatedTableInfo("vehicle", ["submitter_id"]),
            UserRelatedTableInfo("location_entry", ["submitter_id"]),
            UserRelatedTableInfo("regulatory_alert", ["user_id"]),
            UserRelatedTableInfo("regulation_computation", ["user_id"]),
            UserRelatedTableInfo("user_agreement", ["user_id"]),
            UserRelatedTableInfo("refresh_token", ["user_id"]),
            UserRelatedTableInfo("user_read_token", ["user_id"]),
            UserRelatedTableInfo("user_survey_actions", ["user_id"]),
            UserRelatedTableInfo("team_admin_user", ["user_id"]),
            UserRelatedTableInfo("controller_control", ["user_id"]),
        ]

    def _init_dismissable_tables(self) -> Set[str]:
        return {"activity", "comment", "expenditure", "employment"}

    def _get_inactive_companies(self) -> Tuple[int, ...]:
        companies_ceased_siren = set(
            self.anonymizer.find_inactive_companies_by_siren(self.cutoff_date)
        )
        companies_ceased_employment = set(
            self.anonymizer.find_inactive_companies_by_employment(
                self.cutoff_date
            )
        )
        companies_no_recent_missions = set(
            self.anonymizer.find_inactive_companies_by_missions(
                self.cutoff_date
            )
        )

        return tuple(
            companies_ceased_siren.union(
                companies_ceased_employment, companies_no_recent_missions
            )
        )

    def find_inactive_users(self) -> Tuple[Set[int], Set[int]]:
        start_time = time.time()
        logger.info("Starting inactive users search...")

        inactive_admin = set()

        inactive_companies = self._get_inactive_companies()

        sql_query_non_admin = """
        SELECT DISTINCT u.id 
          FROM "user" u
          JOIN employment e ON u.id = e.user_id
         WHERE e.has_admin_rights = false
         AND u.creation_time <= :cutoff_date
         AND NOT EXISTS (
            SELECT 1 
              FROM activity a
             WHERE a.creation_time > :cutoff_date
               AND (
                   a.user_id = u.id OR
                   a.submitter_id = u.id OR
                   a.dismiss_author_id = u.id
                   )
        )
        """

        inactive_non_admin = set(
            row[0]
            for row in db.session.execute(
                sql_query_non_admin, {"cutoff_date": self.cutoff_date}
            )
        )

        if inactive_companies:
            # check if admin is only admin in inactive companies
            sql_query_admin = """
            SELECT DISTINCT u.id 
            FROM "user" u
            JOIN employment e ON u.id = e.user_id
            WHERE e.has_admin_rights = true
            AND u.creation_time <= :cutoff_date
            AND NOT EXISTS (
               SELECT 1 
               FROM activity a
               WHERE a.creation_time > :cutoff_date
               AND (
                    a.user_id = u.id OR
                    a.submitter_id = u.id OR
                    a.dismiss_author_id = u.id
                    )
            )
            AND NOT EXISTS (
               SELECT 1 
                 FROM employment ee
                WHERE ee.user_id = u.id
                  AND ee.has_admin_rights = true
                  AND ee.company_id NOT IN :inactive_companies
            )
            """

            inactive_admin = set(
                row[0]
                for row in db.session.execute(
                    sql_query_admin,
                    {
                        "cutoff_date": self.cutoff_date,
                        "inactive_companies": inactive_companies,
                    },
                )
            )

        sql_query_controller = """
        SELECT DISTINCT cu.id 
          FROM controller_user cu
          LEFT JOIN controller_control cc ON cu.id = cc.controller_id
         WHERE cu.creation_time <= :cutoff_date
         AND NOT EXISTS (
            SELECT 1 
              FROM controller_control cc2
             WHERE cc2.creation_time > :cutoff_date
               AND cc2.controller_id = cu.id
        )
        """

        inactive_controllers = set(
            row[0]
            for row in db.session.execute(
                sql_query_controller, {"cutoff_date": self.cutoff_date}
            )
        )

        all_inactive_users = inactive_non_admin | inactive_admin

        logger.info(
            f"Found {len(all_inactive_users)} inactive users "
            f"({len(inactive_non_admin)} non-admin, {len(inactive_admin)} admin) "
            f"Found {len(inactive_controllers)} inactive controller "
            f"in {time.time() - start_time:.2f}s"
        )

        return all_inactive_users, inactive_controllers

    def _build_find_active_relations_query(
        self, table_info: UserRelatedTableInfo
    ) -> str:

        conditions = " OR ".join(
            [f"t.{col} = iu.id" for col in table_info.user_columns]
        )

        case_statements = " ".join(
            [
                f"WHEN t.{col} != iu.id THEN t.{col}"
                for col in table_info.user_columns
            ]
        )
        related_user_id = f"(CASE {case_statements} END)"

        dismissables_entities = ""
        if table_info.table_name in self.dismissable_tables:
            dismissables_entities = "t.dismissed_at IS NULL AND"

        array_of_inactive_user_ids = "ALL(SELECT UNNEST(:inactive_user_ids))"

        sql_query = f"""
            WITH active_relations AS (
                SELECT DISTINCT
                    iu.id as inactive_user_id,
                    {related_user_id} as related_user_id
                FROM unnest(:user_ids) as iu(id)
                JOIN {table_info.table_name} t ON ({conditions})
                WHERE
                    {dismissables_entities}
                    {related_user_id} IS NOT NULL
                    AND {related_user_id} != {array_of_inactive_user_ids}
            )
            SELECT DISTINCT inactive_user_id
            FROM active_relations
        """

        return sql_query

    def classify_users_for_anonymization(self) -> Dict[str, Set[int]]:
        start_time = time.time()
        logger.info("Begin Classification...")

        inactive_users, inactive_controllers = self.find_inactive_users()

        full_anonymization = set(inactive_users)
        partial_anonymization = set()

        for table_info in self.user_related_tables:
            if not full_anonymization:
                break

            table_start = time.time()
            logger.info(f"Check table {table_info.table_name}...")

            sql_query = self._build_find_active_relations_query(table_info)

            results = db.session.execute(
                sql_query,
                {
                    "user_ids": list(full_anonymization),
                    "inactive_user_ids": list(inactive_users),
                },
            )

            users_with_active_relations = set(row[0] for row in results)

            if users_with_active_relations:
                full_anonymization -= users_with_active_relations
                partial_anonymization.update(users_with_active_relations)

            logger.info(
                f"Table {table_info.table_name} checked in {time.time() - table_start:.2f}s"
            )
            logger.info(
                f"Status: {len(full_anonymization)} full, {len(partial_anonymization)} partial"
            )

        total_time = time.time() - start_time
        logger.info(f"Classification done in {total_time:.2f}s")

        logger.info("Classification summary:")
        logger.info(f"Total inactive users: {len(inactive_users)}")
        logger.info(
            f"Users ready for full anonymization: {len(full_anonymization)}"
        )
        logger.info(
            f"Users requiring partial anonymization: {len(partial_anonymization)}"
        )
        logger.info(f"Total inactive controllers: {len(inactive_controllers)}")

        return {
            "user_full_anonymization": full_anonymization,
            "user_partial_anonymization": partial_anonymization,
            "controller_user_anonymization": inactive_controllers,
        }
