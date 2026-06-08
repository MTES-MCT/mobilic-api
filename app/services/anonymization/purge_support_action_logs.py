import logging
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta

from app import app, db
from app.models.support_action_log import SupportActionLog

logger = logging.getLogger(__name__)


def purge_expired_support_action_logs(dry_run=False):
    cutoff = datetime.now(tz=timezone.utc) - relativedelta(
        months=app.config["SUPPORT_LOG_RETENTION_MONTHS"],
    )
    query = SupportActionLog.query.filter(
        SupportActionLog.creation_time < cutoff
    )
    count = query.count()
    if count == 0:
        logger.info("No expired support_action_log rows")
        return 0
    if dry_run:
        logger.info(
            "Dry run: would purge %d support_action_log rows older than %s",
            count,
            cutoff.date(),
        )
        return count
    try:
        deleted = query.delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    logger.info(
        "Purged %d support_action_log rows older than %s",
        deleted,
        cutoff.date(),
    )
    return deleted
