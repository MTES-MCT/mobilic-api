import logging

from app import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

DEFAULT_K = 2


def apply_activity_k_anonymity(k: int = DEFAULT_K) -> int:
    if k < 2:
        raise ValueError("k must be >= 2 to provide any anonymity")

    victims = [
        row[0]
        for row in db.session.execute(
            text(
                """
                SELECT user_id FROM anon_activity
                GROUP BY user_id
                HAVING count(*) IN (
                    SELECT cnt FROM (
                        SELECT count(*) AS cnt FROM anon_activity GROUP BY user_id
                    ) counts
                    GROUP BY cnt HAVING count(*) < :k
                )
                """
            ),
            {"k": k},
        )
    ]

    if not victims:
        logger.info("k-anonymity: no user removed (k=%s)", k)
        return 0

    db.session.execute(
        text(
            """
            DELETE FROM anon_activity_version
            WHERE activity_id IN (
                SELECT id FROM anon_activity WHERE user_id = ANY(:uids)
            )
            """
        ),
        {"uids": victims},
    )
    result = db.session.execute(
        text("DELETE FROM anon_activity WHERE user_id = ANY(:uids)"),
        {"uids": victims},
    )
    db.session.commit()

    deleted = result.rowcount or 0
    logger.info(
        "k-anonymity: removed %s users (%s anon_activity rows) at k=%s",
        len(victims),
        deleted,
        k,
    )
    return deleted
