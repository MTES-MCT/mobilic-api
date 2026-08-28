import logging
from datetime import datetime, timedelta

import redis as redis_module

from app import app
from app.helpers.celery import celery
from app.models.activity import Activity, ActivityType
from app.domain.push_notification import send_push_notification

logger = logging.getLogger(__name__)

WORK_ACTIVITY_TYPES = {
    ActivityType.DRIVE,
    ActivityType.WORK,
    ActivityType.SUPPORT,
    ActivityType.TRANSFER,
}

ALERT_BEFORE_LIMIT = timedelta(minutes=15)
MAX_UNINTERRUPTED_WORK = timedelta(hours=6)
ALERT_DELAY = MAX_UNINTERRUPTED_WORK - ALERT_BEFORE_LIMIT

REDIS_KEY_PREFIX = "break_alert_sent"
REDIS_KEY_TTL = int(MAX_UNINTERRUPTED_WORK.total_seconds()) + 3600

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_module.Redis.from_url(
            app.config["CELERY_BROKER_URL"],
            socket_connect_timeout=3,
            socket_timeout=3,
        )
    return _redis_client


def _sent_key(user_id, work_start_ts):
    return f"{REDIS_KEY_PREFIX}:{user_id}:{work_start_ts}"


@celery.task()
def send_break_alert_task(user_id, activity_id, work_start_ts):
    with app.app_context():
        activity = Activity.query.get(activity_id)
        if not activity:
            return

        if activity.is_dismissed or activity.end_time:
            logger.info(
                f"Activity {activity_id} ended or dismissed, skipping alert"
            )
            return

        if activity.type not in WORK_ACTIVITY_TYPES:
            return

        try:
            redis = _get_redis()
            key = _sent_key(user_id, work_start_ts)
            was_set = redis.set(key, "1", nx=True, ex=REDIS_KEY_TTL)
            if not was_set:
                logger.info(
                    f"Break alert already sent for user {user_id} "
                    f"(work_start_ts={work_start_ts}), skipping"
                )
                return
        except Exception:
            logger.warning("Redis unavailable, skipping alert")
            return

        send_push_notification(
            user_id=user_id,
            title="Alerte pause obligatoire",
            body=(
                "Vous allez atteindre les 6 heures maximum "
                "de travail ininterrompu. "
                "Arrêtez-vous pour vous reposer."
            ),
        )
        logger.info(f"Break alert sent to user {user_id}")


def get_uninterrupted_work_start(user, mission, current_start_time):
    activities = sorted(
        [
            a
            for a in mission.activities_for(user)
            if a.type in WORK_ACTIVITY_TYPES
            and not a.is_dismissed
            and a.end_time
        ],
        key=lambda a: a.start_time,
    )

    work_start = current_start_time
    for i in range(len(activities) - 1, -1, -1):
        a = activities[i]
        if a.start_time >= current_start_time:
            continue
        if a.end_time >= work_start:
            work_start = a.start_time
        else:
            break
    return work_start


MAX_DELAY_FOR_REAL_TIME = timedelta(minutes=5)


def schedule_break_alert_if_needed(user_id, activity, reception_time=None):
    if activity.type not in WORK_ACTIVITY_TYPES:
        return

    now = reception_time or datetime.now()
    if (now - activity.start_time) > MAX_DELAY_FOR_REAL_TIME:
        return

    mission = activity.mission
    user = activity.user

    work_start = get_uninterrupted_work_start(
        user, mission, activity.start_time
    )
    work_start_ts = int(work_start.timestamp())
    if work_start == activity.start_time:
        alert_time = activity.start_time + ALERT_DELAY
    else:
        elapsed = now - work_start
        remaining = ALERT_DELAY - elapsed
        alert_time = now + remaining if remaining.total_seconds() > 0 else now

    send_break_alert_task.apply_async(
        args=[user_id, activity.id, work_start_ts],
        eta=alert_time,
    )
    logger.info(
        f"Break alert scheduled for user {user_id} "
        f"at {alert_time} (work started at {work_start})"
    )
