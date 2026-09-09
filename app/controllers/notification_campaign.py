import graphene
from datetime import datetime, timezone

from sqlalchemy import or_

from app import db
from app.controllers.utils import atomic_transaction, Void
from app.data_access.notification_campaign import (
    NotificationCampaignOutput,
)
from app.helpers.authentication import (
    AuthenticatedMutation,
    current_user,
)
from app.helpers.authorization import (
    admin_or_bizdev,
    with_authorization_policy,
)
from app.helpers.errors import InvalidParamsError
from app.helpers.graphene_types import (
    TimeStamp,
    graphene_enum_type,
)
from app.jobs.notification_campaign import send_campaign_task
from app.models import User, Employment
from app.models.employment import (
    EmploymentRequestValidationStatus,
)
from app.models.notification_campaign import (
    CampaignStatus,
    CampaignTargetType,
    NotificationCampaign,
)

MAX_TITLE_LENGTH = 100
MAX_BODY_LENGTH = 500
PAGE_SIZE = 20


class CreateNotificationCampaign(AuthenticatedMutation):
    """Crée et lance une campagne de notifications push."""

    class Arguments:
        title = graphene.String(required=True)
        body = graphene.String(required=True)
        target_type = graphene.Argument(
            graphene_enum_type(CampaignTargetType),
            required=True,
        )
        target_user_ids = graphene.List(
            graphene.Int, required=False
        )
        scheduled_at = TimeStamp(required=False)

    Output = NotificationCampaignOutput

    @classmethod
    @with_authorization_policy(admin_or_bizdev)
    def mutate(
        cls,
        _,
        info,
        title,
        body,
        target_type,
        target_user_ids=None,
        scheduled_at=None,
    ):
        title = title.strip()
        body = body.strip()

        if not title or len(title) > MAX_TITLE_LENGTH:
            raise InvalidParamsError(
                f"Le titre doit faire entre 1 et "
                f"{MAX_TITLE_LENGTH} caractères"
            )
        if not body or len(body) > MAX_BODY_LENGTH:
            raise InvalidParamsError(
                f"Le message doit faire entre 1 et "
                f"{MAX_BODY_LENGTH} caractères"
            )

        is_specific = target_type in (
            CampaignTargetType.SPECIFIC_EMPLOYEES.value,
            CampaignTargetType.SPECIFIC_MANAGERS.value,
        )
        if is_specific and not target_user_ids:
            raise InvalidParamsError(
                "La liste des destinataires est requise "
                "pour un ciblage spécifique"
            )
        if not is_specific and target_user_ids:
            raise InvalidParamsError(
                "La liste des destinataires ne doit pas "
                "être fournie pour un ciblage global"
            )

        if scheduled_at:
            scheduled_dt = scheduled_at.replace(
                tzinfo=timezone.utc
            )
            if scheduled_dt <= datetime.now(timezone.utc):
                raise InvalidParamsError(
                    "La date d'envoi doit être dans le futur"
                )
        else:
            scheduled_dt = None

        with atomic_transaction(commit_at_end=True):
            campaign = NotificationCampaign(
                created_by_id=current_user.id,
                title=title,
                body=body,
                target_type=target_type,
                target_user_ids=target_user_ids,
                scheduled_at=scheduled_dt,
                status=CampaignStatus.DRAFT,
            )
            db.session.add(campaign)

        try:
            if scheduled_dt:
                result = send_campaign_task.apply_async(
                    args=[campaign.id], eta=scheduled_dt
                )
            else:
                result = send_campaign_task.apply_async(
                    args=[campaign.id]
                )
            campaign.celery_task_id = result.id
            db.session.commit()
        except Exception:
            campaign.status = CampaignStatus.FAILED
            db.session.commit()
            raise InvalidParamsError(
                "Erreur lors de la programmation de l'envoi"
            )

        return campaign


class CancelNotificationCampaign(AuthenticatedMutation):
    """Annule une campagne de notifications programmée."""

    class Arguments:
        campaign_id = graphene.Int(required=True)

    Output = NotificationCampaignOutput

    @classmethod
    @with_authorization_policy(admin_or_bizdev)
    def mutate(cls, _, info, campaign_id):
        campaign = NotificationCampaign.query.get(campaign_id)
        if not campaign:
            raise InvalidParamsError("Campagne introuvable")
        if campaign.status != CampaignStatus.DRAFT:
            raise InvalidParamsError(
                "Seules les campagnes en attente "
                "peuvent être annulées"
            )

        if campaign.celery_task_id:
            from app.helpers.celery import celery

            celery.control.revoke(campaign.celery_task_id)

        with atomic_transaction(commit_at_end=True):
            campaign.status = CampaignStatus.CANCELLED

        return campaign


MAX_BANNER_TEXT_LENGTH = 500


class UpdatePushBannerText(AuthenticatedMutation):
    """Modifie le texte du bandeau de souscription push."""

    class Arguments:
        banner_text = graphene.String(required=True)

    Output = Void

    @classmethod
    @with_authorization_policy(admin_or_bizdev)
    def mutate(cls, _, info, banner_text):
        banner_text = banner_text.strip()
        if not banner_text or len(banner_text) > MAX_BANNER_TEXT_LENGTH:
            raise InvalidParamsError(
                f"Le texte doit faire entre 1 et "
                f"{MAX_BANNER_TEXT_LENGTH} caractères"
            )

        from app.models.push_banner_config import (
            PushBannerConfig,
        )

        with atomic_transaction(commit_at_end=True):
            config = PushBannerConfig.get_current()
            if config:
                config.banner_text = banner_text
                config.updated_at = datetime.now(timezone.utc)
                config.updated_by_id = current_user.id
            else:
                config = PushBannerConfig(
                    id=PushBannerConfig.SINGLETON_ID,
                    banner_text=banner_text,
                    updated_at=datetime.now(timezone.utc),
                    updated_by_id=current_user.id,
                )
                db.session.add(config)

        return Void(success=True)


class CampaignSearchResult(graphene.ObjectType):
    id = graphene.Int()
    email = graphene.String()
    first_name = graphene.String()
    last_name = graphene.String()


class CampaignSearchResultPage(graphene.ObjectType):
    results = graphene.List(CampaignSearchResult)
    has_more = graphene.Boolean()


class NotificationCampaignListPage(graphene.ObjectType):
    results = graphene.List(NotificationCampaignOutput)
    has_more = graphene.Boolean()


class Query(graphene.ObjectType):
    notification_campaigns = graphene.Field(
        NotificationCampaignListPage,
        offset=graphene.Int(default_value=0),
        limit=graphene.Int(default_value=20),
    )

    search_users_for_campaign = graphene.Field(
        CampaignSearchResultPage,
        search=graphene.String(required=True),
        target_type=graphene.Argument(
            graphene_enum_type(CampaignTargetType),
            required=False,
        ),
        offset=graphene.Int(default_value=0),
    )

    @with_authorization_policy(admin_or_bizdev)
    def resolve_notification_campaigns(
        self, info, offset=0, limit=20
    ):
        limit = min(limit, 50)
        campaigns = (
            NotificationCampaign.query.order_by(
                NotificationCampaign.creation_time.desc()
            )
            .offset(offset)
            .limit(limit + 1)
            .all()
        )
        has_more = len(campaigns) > limit
        return NotificationCampaignListPage(
            results=campaigns[:limit], has_more=has_more
        )

    @with_authorization_policy(admin_or_bizdev)
    def resolve_search_users_for_campaign(
        self, info, search, target_type=None, offset=0
    ):
        from datetime import date

        if len(search) < 3:
            return CampaignSearchResultPage(
                results=[], has_more=False
            )

        escaped = (
            search.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        term = f"%{escaped}%"
        today = date.today()

        user_filters = or_(
            User.email.ilike(term, escape="\\"),
            User.first_name.ilike(term, escape="\\"),
            User.last_name.ilike(term, escape="\\"),
        )

        query = User.query.filter(user_filters)

        active_employment_filter = [
            Employment.validation_status
            == EmploymentRequestValidationStatus.APPROVED,
            Employment.is_dismissed == False,
            Employment.start_date <= today,
            or_(
                Employment.end_date.is_(None),
                Employment.end_date >= today,
            ),
        ]

        if target_type in (
            CampaignTargetType.SPECIFIC_EMPLOYEES.value,
            CampaignTargetType.ALL_EMPLOYEES.value,
        ):
            query = query.filter(
                User.id.in_(
                    db.session.query(Employment.user_id)
                    .filter(
                        *active_employment_filter,
                        or_(
                            Employment.has_admin_rights.is_(
                                None
                            ),
                            Employment.has_admin_rights
                            == False,
                        ),
                    )
                    .distinct()
                )
            )
        elif target_type in (
            CampaignTargetType.SPECIFIC_MANAGERS.value,
            CampaignTargetType.ALL_MANAGERS.value,
        ):
            query = query.filter(
                User.id.in_(
                    db.session.query(Employment.user_id)
                    .filter(
                        *active_employment_filter,
                        Employment.has_admin_rights == True,
                    )
                    .distinct()
                )
            )

        users = (
            query.offset(offset)
            .limit(PAGE_SIZE + 1)
            .all()
        )
        has_more = len(users) > PAGE_SIZE
        return CampaignSearchResultPage(
            results=[
                CampaignSearchResult(
                    id=u.id,
                    email=u.email,
                    first_name=u.first_name,
                    last_name=u.last_name,
                )
                for u in users[:PAGE_SIZE]
            ],
            has_more=has_more,
        )
