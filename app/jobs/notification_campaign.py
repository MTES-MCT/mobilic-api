import hashlib
import hmac
import logging
from datetime import date, datetime, timezone

from sqlalchemy import or_

from app import app, db
from app.helpers.celery import celery
from app.domain.push_notification import send_push_notification
from app.models.employment import (
    Employment,
    EmploymentRequestValidationStatus,
)
from app.models.notification_campaign import (
    CampaignStatus,
    CampaignTargetType,
    NotificationCampaign,
)
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)

# persist counters every N sends to track progress
BATCH_COMMIT_SIZE = 100


def generate_click_token(campaign_id):
    secret = app.config.get("JWT_SECRET_KEY", "")
    return hmac.new(
        secret.encode(),
        str(campaign_id).encode(),
        hashlib.sha256,
    ).hexdigest()


def _get_target_user_ids(campaign):
    today = date.today()

    active_filter = [
        Employment.validation_status
        == EmploymentRequestValidationStatus.APPROVED,
        Employment.start_date <= today,
        or_(
            Employment.end_date.is_(None),
            Employment.end_date >= today,
        ),
        Employment.is_dismissed == False,
        Employment.user_id.isnot(None),
    ]

    if campaign.target_type == CampaignTargetType.ALL_EMPLOYEES:
        active_filter.append(
            or_(
                Employment.has_admin_rights.is_(None),
                Employment.has_admin_rights == False,
            )
        )
    elif campaign.target_type == CampaignTargetType.ALL_MANAGERS:
        active_filter.append(Employment.has_admin_rights == True)

    if campaign.target_type in (
        CampaignTargetType.SPECIFIC_EMPLOYEES,
        CampaignTargetType.SPECIFIC_MANAGERS,
    ):
        user_ids = campaign.target_user_ids or []
    else:
        user_ids = [
            row[0]
            for row in db.session.query(Employment.user_id)
            .filter(*active_filter)
            .distinct()
            .all()
        ]

    subscribed = {
        row[0]
        for row in db.session.query(PushSubscription.user_id)
        .filter(PushSubscription.user_id.in_(user_ids))
        .distinct()
        .all()
    }
    notifiable = [uid for uid in user_ids if uid in subscribed]
    return user_ids, notifiable


@celery.task(bind=True)
def send_campaign_task(self, campaign_id):
    with app.app_context():
        campaign = NotificationCampaign.query.get(campaign_id)
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return

        if campaign.status != CampaignStatus.DRAFT:
            logger.info(
                f"Campaign {campaign_id} status is "
                f"{campaign.status}, skipping"
            )
            return

        campaign.status = CampaignStatus.SENDING
        campaign.celery_task_id = self.request.id
        db.session.commit()

        try:
            all_targeted, user_ids = _get_target_user_ids(
                campaign
            )
            campaign.targeted_count = len(all_targeted)
            campaign.total_recipients = len(user_ids)
            db.session.commit()

            click_token = generate_click_token(campaign_id)
            sent = 0
            failed = 0

            for i, user_id in enumerate(user_ids):
                ok = send_push_notification(
                    user_id=user_id,
                    title=campaign.title,
                    body=campaign.body,
                    data={
                        "campaignId": campaign_id,
                        "clickToken": click_token,
                    },
                )
                if ok:
                    sent += 1
                else:
                    failed += 1

                if (i + 1) % BATCH_COMMIT_SIZE == 0:
                    campaign.sent_count = sent
                    campaign.failed_count = failed
                    db.session.commit()

            campaign.sent_count = sent
            campaign.failed_count = failed
            campaign.status = CampaignStatus.SENT
            campaign.completed_at = datetime.now(timezone.utc)
            db.session.commit()

            logger.info(
                f"Campaign {campaign_id} completed: "
                f"{sent} sent, {failed} failed"
            )

        except Exception as e:
            logger.error(
                f"Campaign {campaign_id} failed: {e}"
            )
            db.session.rollback()
            campaign = NotificationCampaign.query.get(
                campaign_id
            )
            campaign.status = CampaignStatus.FAILED
            db.session.commit()
