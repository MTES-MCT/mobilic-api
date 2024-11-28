import logging
import csv
from io import StringIO
from sqlalchemy import text
from app import db
import json

logger = logging.getLogger(__name__)


def migrate_anonymized_data(interval: str, verbose=False):
    if verbose:
        logger.setLevel(logging.DEBUG)

    connection = db.get_engine().raw_connection()
    cursor = connection.cursor()

    try:
        logger.debug(f"Migrate mission for interval: {interval}")
        migrated_mission_ids = migrate_anonymized_mission(
            interval, connection, cursor
        )

        logger.debug("Migrate activity for migrated missions")
        migrated_activity_ids = migrate_anonymized_activity(
            migrated_mission_ids, connection, cursor
        )

        logger.debug("Migrate activity version for migrated activities")
        migrate_anonymized_activity_version(
            migrated_activity_ids, connection, cursor
        )

        logger.debug("Migrate expenditure for migrated mission")
        migrate_anonymized_expenditure(
            migrated_mission_ids, connection, cursor
        )

        logger.debug("Delete original data")
        delete_original_data(
            migrated_mission_ids, migrated_activity_ids, connection
        )

        logger.debug(f"Migration complete for interval: {interval}")
        connection.commit()

    except ValueError as e:
        logger.error(f"Error during migration for interval '{interval}': {e}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()


def migrate_anonymized_mission(interval: str, connection, cursor):
    select_query = f"""
        SELECT 
            id,
            anon.fake_last_name() AS name,
            NULL AS submitter_id,
            NULL AS company_id,
            vehicle_id,
            date_trunc('month', creation_time) AS creation_time,
            date_trunc('month', reception_time) AS reception_time,
            context::jsonb AS context
        FROM mission
        WHERE creation_time {interval};
    """

    result = db.session.execute(text(select_query))
    rows = result.fetchall()

    if not rows:
        print("No mission data to migrate.")
        return []

    csv_buffer = StringIO()
    csv_writer = csv.writer(csv_buffer)

    migrated_mission_ids = []
    for row in rows:
        row_as_list = list(row)
        migrated_mission_ids.append(row_as_list[0])

        if isinstance(row_as_list[-1], dict):
            row_as_list[-1] = json.dumps(row_as_list[-1])

        csv_writer.writerow(row_as_list)

    csv_buffer.seek(0)

    try:
        cursor.copy_expert(
            """
            COPY mission_anonymized (
                id,
                name,
                submitter_id,
                company_id,
                vehicle_id,
                creation_time,
                reception_time,
                context
            )
            FROM STDIN WITH (FORMAT CSV)
            """,
            csv_buffer,
        )

        print("Anonymized mission migration successful.")
        return migrated_mission_ids

    except Exception as e:
        connection.rollback()
        print(f"Error when copying mission data: {e}")
        raise

    finally:
        csv_buffer.close()


def migrate_anonymized_activity(
    migrated_mission_ids: list, connection, cursor
):
    if not migrated_mission_ids:
        print("No mission data to migrate activities for.")
        return []

    # TO DO : garder l'intervalle de temps entre activité pour les stats
    select_query = """
        SELECT 
            id,
            type,
            NULL AS user_id,
            NULL AS submitter_id,
            mission_id,
            NULL AS dismiss_author_id,
            date_trunc('month', dismissed_at) AS dismissed_at,
            date_trunc('month', creation_time) AS creation_time,
            date_trunc('month', reception_time) AS reception_time,
            date_trunc('month', start_time) AS start_time,
            date_trunc('month', end_time) AS end_time,
            date_trunc('month', last_update_time) AS last_update_time,
            NULL AS last_submitter_id,
            dismiss_context::jsonb AS dismiss_context
        FROM activity
        WHERE mission_id = ANY(:mission_ids);
    """

    result = db.session.execute(
        text(select_query), {"mission_ids": migrated_mission_ids}
    )
    rows = result.fetchall()

    if not rows:
        print("No activity data to migrate.")
        return []

    csv_buffer = StringIO()
    csv_writer = csv.writer(csv_buffer)

    migrated_activity_ids = []
    for row in rows:
        row_as_list = list(row)
        migrated_activity_ids.append(row_as_list[0])

        if isinstance(row_as_list[-1], dict):
            row_as_list[-1] = json.dumps(row_as_list[-1])

        csv_writer.writerow(row_as_list)

    csv_buffer.seek(0)

    try:
        cursor.copy_expert(
            """
            COPY activity_anonymized (
                id,
                type,
                user_id,
                submitter_id,
                mission_id,
                dismiss_author_id,
                dismissed_at,
                creation_time,
                reception_time,
                start_time,
                end_time,
                last_update_time,
                last_submitter_id,
                dismiss_context
            )
            FROM STDIN WITH (FORMAT CSV)
            """,
            csv_buffer,
        )

        print("Anonymized activity migration successful.")
        return migrated_activity_ids

    except Exception as e:
        connection.rollback()
        print(f"Error when copying activity data: {e}")
        raise

    finally:
        csv_buffer.close()


def migrate_anonymized_activity_version(
    migrated_activity_ids: list, connection, cursor
):
    if not migrated_activity_ids:
        print("No activity data to migrate versions for.")
        return

    select_query = """
        SELECT 
            id,
            activity_id,
            version_number,
            NULL AS submitter_id,
            date_trunc('month', creation_time) AS creation_time,
            date_trunc('month', reception_time) AS reception_time,
            date_trunc('month', start_time) AS start_time,
            date_trunc('month', end_time) AS end_time,
            context::jsonb AS context
        FROM activity_version
        WHERE activity_id = ANY(:activity_ids);
    """

    result = db.session.execute(
        text(select_query), {"activity_ids": migrated_activity_ids}
    )
    rows = result.fetchall()

    if not rows:
        print("No activity version data to migrate.")
        return

    csv_buffer = StringIO()
    csv_writer = csv.writer(csv_buffer)

    for row in rows:
        row_as_list = list(row)

        if isinstance(row_as_list[-1], dict):
            row_as_list[-1] = json.dumps(row_as_list[-1])

        csv_writer.writerow(row_as_list)

    csv_buffer.seek(0)

    try:
        cursor.copy_expert(
            """
            COPY activity_version_anonymized (
                id,
                activity_id,
                version_number,
                submitter_id,
                creation_time,
                reception_time,
                start_time,
                end_time,
                context
            )
            FROM STDIN WITH (FORMAT CSV)
            """,
            csv_buffer,
        )

        print("Anonymized activity version migration successful.")

    except Exception as e:
        connection.rollback()
        print(f"Error when copying activity version data: {e}")
        raise

    finally:
        csv_buffer.close()


def migrate_anonymized_expenditure(
    migrated_mission_ids: list, connection, cursor
):
    if not migrated_mission_ids:
        print("No expenditure data to migrate versions for.")
        return

    select_query = """
        SELECT 
            id,
            mission_id,
            type,
            NULL AS user_id,
            NULL AS submitter_id,
            NULL AS dismiss_author_id,
            date_trunc('month', creation_time) AS creation_time,
            date_trunc('month', reception_time) AS reception_time,
            date_trunc('month', dismissed_at) AS dismissed_at,
            date_trunc('month', spending_date) AS spending__date,
            dismiss_context::jsonb AS dismiss_context
        FROM expenditure
        WHERE mission_id = ANY(:mission_ids);
    """

    result = db.session.execute(
        text(select_query), {"mission_ids": migrated_mission_ids}
    )
    rows = result.fetchall()

    if not rows:
        print("No expenditure data to migrate.")
        return

    csv_buffer = StringIO()
    csv_writer = csv.writer(csv_buffer)

    for row in rows:
        row_as_list = list(row)

        if isinstance(row_as_list[-1], dict):
            row_as_list[-1] = json.dumps(row_as_list[-1])

        csv_writer.writerow(row_as_list)

    csv_buffer.seek(0)

    try:
        cursor.copy_expert(
            """
            COPY expenditure_anonymized (
                id,
                mission_d,
                type,
                user_id,
                submitter_id,
                dismiss_author_id,
                creation_time,
                reception_time,
                dismissed_at,
                spending__date,
                dismiss_context
            )
            FROM STDIN WITH (FORMAT CSV)
            """,
            csv_buffer,
        )

        print("Anonymized expenditure migration successful.")

    except Exception as e:
        connection.rollback()
        print(f"Error when copying expenditure data: {e}")
        raise

    finally:
        csv_buffer.close()


def delete_original_data(
    migrated_mission_ids, migrated_activity_ids, connection
):
    try:
        delete_activity_version_query = """
            DELETE FROM activity_version WHERE activity_id = ANY(:activity_ids);
        """
        db.session.execute(
            text(delete_activity_version_query),
            {"activity_ids": migrated_activity_ids},
        )

        delete_activity_query = """
            DELETE FROM activity WHERE mission_id = ANY(:mission_ids);
        """
        db.session.execute(
            text(delete_activity_query), {"mission_ids": migrated_mission_ids}
        )

        delete_mission_query = """
            DELETE FROM mission WHERE id = ANY(:ids);
        """
        db.session.execute(
            text(delete_mission_query), {"ids": migrated_mission_ids}
        )

        print("Anonymized data deletion successful.")

    except Exception as e:
        connection.rollback()
        print(f"Error during data deletion: {e}")
        raise
