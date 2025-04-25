from app import db
from typing import Dict, Set, Tuple
from datetime import datetime
import logging
import time

from app.services.anonymization.standalone import DataFinder

logger = logging.getLogger(__name__)


class UserClassifier:
    def __init__(self, cutoff_date: datetime):
        self.cutoff_date = cutoff_date
        self.anonymizer = DataFinder(db.session)

    def _get_inactive_companies(self) -> Tuple[int, ...]:
        companies_without_active_employments = set(
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
            companies_without_active_employments.union(
                companies_no_recent_missions
            )
        )

    def find_inactive_users(self) -> Dict[str, Set[int]]:
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
         AND u.status != 'anonymized'
         AND NOT EXISTS (
            SELECT 1 
              FROM activity a
             WHERE a.creation_time > :cutoff_date
               AND (
                   a.user_id = u.id OR
                   a.submitter_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM activity a2
             WHERE a2.dismissed_at > :cutoff_date
               AND (
                   a2.dismiss_author_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM employment em2
             WHERE em2.dismissed_at > :cutoff_date
               AND (
                   em2.dismiss_author_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM mission_validation mv
             WHERE mv.creation_time > :cutoff_date
               AND (
                   mv.user_id = u.id OR
                   mv.submitter_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM mission_end me
             WHERE me.creation_time > :cutoff_date
               AND (
                   me.user_id = u.id OR
                   me.submitter_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM comment c
             WHERE c.creation_time > :cutoff_date
               AND (
                   c.submitter_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM comment c2
             WHERE c2.dismissed_at > :cutoff_date
               AND (
                   c2.dismiss_author_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM mission m
             WHERE m.creation_time > :cutoff_date
               AND (
                   m.submitter_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM expenditure e
             WHERE e.creation_time > :cutoff_date
               AND (
                   e.user_id = u.id OR
                   e.submitter_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM expenditure e2
             WHERE e2.dismissed_at > :cutoff_date
               AND (
                   e2.dismiss_author_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM company_known_address cka
             WHERE cka.dismissed_at > :cutoff_date
               AND (
                   cka.dismiss_author_id = u.id
                   )
        )
        AND NOT EXISTS (
            SELECT 1 
              FROM third_party_client_company tpcc
             WHERE tpcc.dismissed_at > :cutoff_date
               AND (
                   tpcc.dismiss_author_id = u.id
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
            AND u.status != 'anonymized'
            AND NOT EXISTS (
            SELECT 1 
              FROM activity a
             WHERE a.creation_time > :cutoff_date
               AND (
                   a.user_id = u.id OR
                   a.submitter_id = u.id
                   )
            )
            AND NOT EXISTS (
               SELECT 1 
                 FROM employment ee
                WHERE ee.user_id = u.id
                  AND ee.has_admin_rights = true
                  AND ee.company_id NOT IN :inactive_companies
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM activity a2
                 WHERE a2.dismissed_at > :cutoff_date
                   AND (
                       a2.dismiss_author_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM employment em2
                 WHERE em2.dismissed_at > :cutoff_date
                   AND (
                       em2.dismiss_author_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM mission_validation mv
                 WHERE mv.creation_time > :cutoff_date
                   AND (
                       mv.user_id = u.id OR
                       mv.submitter_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM mission_end me
                 WHERE me.creation_time > :cutoff_date
                   AND (
                       me.user_id = u.id OR
                       me.submitter_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM comment c
                 WHERE c.creation_time > :cutoff_date
                   AND (
                       c.submitter_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM comment c2
                 WHERE c2.dismissed_at > :cutoff_date
                   AND (
                       c2.dismiss_author_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM mission m
                 WHERE m.creation_time > :cutoff_date
                   AND (
                       m.submitter_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM expenditure e
                 WHERE e.creation_time > :cutoff_date
                   AND (
                       e.user_id = u.id OR
                       e.submitter_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM expenditure e2
                 WHERE e2.dismissed_at > :cutoff_date
                   AND (
                       e2.dismiss_author_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM company_known_address cka
                 WHERE cka.dismissed_at > :cutoff_date
                   AND (
                       cka.dismiss_author_id = u.id
                       )
            )
            AND NOT EXISTS (
                SELECT 1 
                  FROM third_party_client_company tpcc
                 WHERE tpcc.dismissed_at > :cutoff_date
                   AND (
                       tpcc.dismiss_author_id = u.id
                       )
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

        return {
            "users": inactive_non_admin,
            "admins": inactive_admin,
            "controllers": inactive_controllers,
        }
