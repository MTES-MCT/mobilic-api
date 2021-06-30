from app.helpers.authorization import authenticated_and_active
from app.helpers.errors import AuthorizationError
from app.helpers.time import get_date_or_today
from app.helpers.authentication import current_user
from app.models import Company, User
from typing import List, Optional
from dataclasses import dataclass, field
from functools import wraps
from datetime import date


def company_admin_at(actor, company_obj_or_id, date_or_datetime=None):
    if not authenticated_and_active(actor):
        return False
    date_ = get_date_or_today(date_or_datetime)
    actor_employments_at_date = actor.employments_at(date_)
    company_id = company_obj_or_id
    if type(company_obj_or_id) is Company:
        company_id = company_obj_or_id.id
    return any(
        [
            e.company_id == company_id and e.has_admin_rights
            for e in actor_employments_at_date
        ]
    )


def belongs_to_company_at(
    actor,
    company_obj_or_id,
    date_or_datetime=None,
    include_pending_invite=True,
):
    date_ = get_date_or_today(date_or_datetime)
    actor_employments_at_date = actor.employments_at(
        date_, with_pending_ones=include_pending_invite
    )
    company_id = company_obj_or_id
    if type(company_obj_or_id) is Company:
        company_id = company_obj_or_id.id
    return any([e.company_id == company_id for e in actor_employments_at_date])


def self_or_company_admin(actor, user_obj_or_id):
    user = user_obj_or_id
    if type(user_obj_or_id) is int:
        user = User.query.get(user_obj_or_id)
    if not user:
        return False
    return actor.id == user.id or company_admin_at(actor, user.primary_company)


def only_self(actor, user_obj_or_id):
    user = user_obj_or_id
    if type(user_obj_or_id) is int:
        user = User.query.get(user_obj_or_id)
    if not user:
        return False
    return actor.id == user.id


def can_actor_log_on_mission_at(actor, mission, date=None):
    if not mission or not authenticated_and_active(actor):
        return False
    return belongs_to_company_at(
        actor, mission.company_id, date, include_pending_invite=False
    )


def can_actor_log_on_mission_for_user_at(actor, user, mission, date=None):
    base_permission = can_actor_log_on_mission_at(
        actor, mission, date
    ) and can_actor_access_mission_at(user, mission, date)
    if not base_permission:
        return False
    if actor == user:
        return True
    if mission.company.allow_team_mode and actor.id == mission.submitter_id:
        return True
    return company_admin_at(actor, mission.company_id, date)


def check_actor_can_log_on_mission_for_user_at(
    actor, user, mission, date=None
):
    if not can_actor_log_on_mission_for_user_at(actor, user, mission, date):
        raise AuthorizationError(
            "Actor is not authorized to perform this operation"
        )


def can_actor_access_mission_at(actor, mission, date=None):
    if not mission:
        return False
    return belongs_to_company_at(
        actor, mission.company_id, date, include_pending_invite=False,
    )


@dataclass
class ConsultationScope:
    all_access: bool = False
    company_ids: List = field(default_factory=list)
    max_activity_date: Optional[date] = None
    min_activity_date: Optional[date] = None


def get_activity_consultation_scope(actor, user=None) -> ConsultationScope:
    if user and actor.id == user.id:
        return ConsultationScope(all_access=True)
    return ConsultationScope(
        company_ids=actor.current_company_ids_with_admin_rights
    )


def user_resolver_with_consultation_scope(error_message="Forbidden access"):
    def decorator(resolver):
        @wraps(resolver)
        def wrapper(user, info, *args, **kwargs):
            consultation_scope = get_activity_consultation_scope(
                current_user, user
            )

            company_further_scoping = getattr(
                info.context, "company_ids_scope", None
            )
            if company_further_scoping:
                consultation_scope.company_ids = [
                    cid
                    for cid in consultation_scope.company_ids
                    if cid in company_further_scoping
                ]

            if (
                not consultation_scope.all_access
                and not consultation_scope.company_ids
            ):
                raise AuthorizationError(error_message)

            consultation_scope.max_activity_date = getattr(
                info.context, "max_activity_date", None
            )
            consultation_scope.min_activity_date = getattr(
                info.context, "min_activity_date", None
            )

            kwargs["consultation_scope"] = consultation_scope

            return resolver(user, info, *args, **kwargs)

        return wrapper

    return decorator
