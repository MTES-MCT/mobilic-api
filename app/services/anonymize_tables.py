import csv
from io import StringIO
from sqlalchemy import text
from app import db
import json


def migrate_anonymize_mission(interval: str):
    select_query = f"""
        SELECT 
            id,
            anon.fake_last_name() AS name,
            NULL AS submitter_id,
            NULL AS company_id,
            vehicle_id,
            date_trunc('month', creation_time) AS creation_time,
            date_trunc('month', reception_time) AS reception_time,
            context::jsonb AS context  -- Convertir context en JSON valide
        FROM mission
        WHERE creation_time {interval};
    """

    try:
        with db.session.begin_nested():

            result = db.session.execute(text(select_query))
            rows = result.fetchall()

            if not rows:
                print("No data to migrate.")
                return

            csv_buffer = StringIO()
            csv_writer = csv.writer(csv_buffer)

            for row in rows:
                row_as_list = list(row)

                if isinstance(row_as_list[-1], dict):
                    row_as_list[-1] = json.dumps(row_as_list[-1])

                csv_writer.writerow(row_as_list)

            csv_buffer.seek(0)

            engine = db.get_engine()
            connection = engine.raw_connection()

            try:
                cursor = connection.cursor()
                cursor.copy_expert(
                    """
                    COPY mission_anonymized (id, name, submitter_id, company_id, vehicle_id, creation_time, reception_time, context)
                    FROM STDIN WITH (FORMAT CSV)
                    """,
                    csv_buffer,
                )

                delete_query = f"""
                    DELETE FROM mission WHERE creation_time {interval};
                """
                db.session.execute(text(delete_query))

                print("Anonymized data migration successful.")

            except Exception as e:
                connection.rollback()
                print(f"Error when copying mass data: {e}")
                raise

            finally:
                cursor.close()
                connection.close()
                csv_buffer.close()

    except Exception as e:
        db.session.rollback()
        print(f"Transaction failed, rolling back changes: {e}")

    finally:
        db.session.close()
