from datetime import datetime

import sqlalchemy as sa

from app.models.user_agreement import CGU_INITIAL_VERSION

INITIAL_TIME = datetime(2022, 1, 1)


def init_user_agreement(session, cgu_version=""):
    if cgu_version == "":
        cgu_version = CGU_INITIAL_VERSION

    session.execute(
        sa.text(
            """
            INSERT INTO user_agreement (user_id, cgu_version, creation_time, answer_date, status, is_blacklisted)
            SELECT 
                u.id AS user_id,
                :cgu_version AS cgu_version,
                :creation_time AS creation_time,
                :answer_date AS answer_date,
                'accepted' AS status,
                FALSE AS is_blacklisted
            FROM "user" u
            """
        ).params(
            cgu_version=cgu_version,
            creation_time=INITIAL_TIME,
            answer_date=INITIAL_TIME,
        )
    )
