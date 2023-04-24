from dataclasses import dataclass, field
from datetime import date
from functools import wraps
from typing import List, Optional

from flask import g

from app.helpers.authentication import current_user
from app.helpers.authorization import (
    active,
    controller_only,
    check_company_id_against_scope,
)
from app.helpers.errors import (
    ActivityOutsideEmploymentByAdminError,
    ActivityOutsideEmploymentByEmployeeError,
    AuthorizationError,
    MissionAlreadyValidatedByAdminError,
    MissionAlreadyValidatedByUserError,
    UserNotEmployedByCompanyAnymoreEmployeeError,
    UserNotEmployedByCompanyAnymoreAdminError,
)
from app.helpers.time import get_date_or_today
from app.models import Company, User, Employment
from app.models.controller_control import ControllerControl


def company_admin(actor, company_obj_or_id):
    if not active(actor):
        return False

    today = date.today()

    actor_employments_on_period = actor.active_employments_at(today)
    company_id = company_obj_or_id
    if type(company_obj_or_id) is Company:
        company_id = company_obj_or_id.id

    check_company_id_against_scope(company_id)
    return any(
        [
            e.company_id == company_id and e.has_admin_rights
            for e in actor_employments_on_period
        ]
    )


def companies_admin(actor, company_ids):
    for company_id in company_ids:
        if not company_admin(actor, company_id):
            return False
    return True


def get_employment_over_period(
    actor,
    company_obj_or_id,
    start=None,
    end=None,
    include_pending_invite=True,
):
    start_ = get_date_or_today(start)
    end_ = get_date_or_today(end)
    actor_employments_on_period = actor.active_employments_between(
        start_, end_, include_pending_ones=include_pending_invite
    )
    company_id = company_obj_or_id
    if type(company_obj_or_id) is Company:
        company_id = company_obj_or_id.id

    check_company_id_against_scope(company_id)

    company_employments_on_period = sorted(
        [e for e in actor_employments_on_period if e.company_id == company_id],
        key=lambda e: e.start_date,
    )

    if not company_employments_on_period:
        return None
    earliest_employment = company_employments_on_period[0]
    latest_employment = company_employments_on_period[-1]

    if earliest_employment.start_date > start_ or (
        latest_employment.end_date and latest_employment.end_date < end_
    ):
        return None
    return latest_employment


def is_employed_by_company_over_period(
    actor,
    company_obj_or_id,
    start=None,
    end=None,
    include_pending_invite=True,
):
    return (
        get_employment_over_period(
            actor,
            company_obj_or_id,
            start,
            end,
            include_pending_invite,
        )
        is not None
    )


def has_any_employment_with_company_or_controller(actor, company_obj_or_id):
    if controller_only(actor):
        return True
    company_id = company_obj_or_id
    if type(company_obj_or_id) is Company:
        company_id = company_obj_or_id.id

    return any(
        [
            e.company_id == company_id
            for e in actor.employments
            if e.is_not_rejected and not e.is_dismissed
        ]
    )


def self_or_have_common_company(actor, user_obj_or_id):
    user = user_obj_or_id
    if type(user_obj_or_id) is int:
        user = User.query.get(user_obj_or_id)
    if not user:
        return False
    if actor.id == user.id:
        return True
    current_actor_companies = [
        e.company for e in actor.active_employments_at(date.today())
    ]
    all_lifetime_user_companies = [
        e.company for e in user.employments if e.is_not_rejected
    ]
    return bool(
        set(current_actor_companies) & set(all_lifetime_user_companies)
    )


def only_self(actor, user_obj_or_id):
    user = user_obj_or_id
    if type(user_obj_or_id) is int:
        user = User.query.get(user_obj_or_id)
    if not user:
        return False
    return actor.id == user.id


def only_self_employment(actor, employment_obj_or_id):
    employment = employment_obj_or_id
    if type(employment_obj_or_id) is int:
        employment = Employment.query.get(employment_obj_or_id)
    if not employment:
        return False
    return actor.id == employment.user_id


def _is_actor_allowed_to_access_mission(actor, mission):
    return (
        company_admin(actor, mission.company_id)
        or actor.id == mission.submitter_id
        or len(
            mission.activities_for(actor, include_dismissed_activities=True)
        )
        > 0
    )


def can_actor_read_mission(actor, mission):
    check_company_id_against_scope(mission.company_id)
    return _is_actor_allowed_to_access_mission(actor, mission)


def _raise_authorization_error():
    raise AuthorizationError(
        "Actor is not authorized to perform the operation"
    )


def check_actor_can_write_on_mission_over_period(
    actor, mission, for_user=None, start=None, end=None
):
    # 1. Check that actor has activated account
    if not mission or not active(actor):
        _raise_authorization_error()

    # 2. Check that actor is allowed to access mission (must be a company admin, the mission submitter or have activities on the mission)
    if not _is_actor_allowed_to_access_mission(actor, mission):
        _raise_authorization_error()

    # 3. Check that the eventual user can work on the mission over the period :
    if for_user and not is_employed_by_company_over_period(
        for_user,
        mission.company_id,
        start=start,
        end=end,
        include_pending_invite=False,
    ):
        if for_user == actor:
            raise ActivityOutsideEmploymentByEmployeeError()
        else:
            raise ActivityOutsideEmploymentByAdminError()

    # 3bis. Check that the eventual user is currently employed in company
    if for_user and not is_employed_by_company_over_period(
        for_user,
        mission.company_id,
        include_pending_invite=False,
    ):
        if for_user == actor:
            raise UserNotEmployedByCompanyAnymoreEmployeeError()
        else:
            raise UserNotEmployedByCompanyAnymoreAdminError()

    is_actor_company_admin = company_admin(actor, mission.company_id)
    # 4. Check that actor can log for the eventual user (must be either a company admin, the user himself or the team leader)
    if (
        for_user
        and not is_actor_company_admin
        and not (
            actor == for_user
            or (
                (
                    mission.company.allow_team_mode
                    or len(
                        mission.activities_for(
                            for_user, include_dismissed_activities=True
                        )
                    )
                    > 0
                )
                and actor.id == mission.submitter_id
            )
        )
    ):
        _raise_authorization_error()

    # 5. Check that the mission is not yet validated by an admin
    if mission.validated_by_admin or (
        for_user and mission.validated_by_admin_for(for_user)
    ):
        raise MissionAlreadyValidatedByAdminError()

    # 6. Check that the mission is not yet validated by the person concerned by the edition (user or actor)
    if not is_actor_company_admin:
        if mission.validation_of(for_user or actor):
            raise MissionAlreadyValidatedByUserError()

    return True


def check_actor_can_write_on_mission_for_user(actor, mission_user_tuple):
    return check_actor_can_write_on_mission_over_period(
        actor,
        mission=mission_user_tuple.get("mission"),
        for_user=mission_user_tuple.get("for_user"),
    )


def check_actor_can_edit_activity(actor, activity):
    check_company_id_against_scope(activity.mission.company_id)
    return activity and (
        actor.id == activity.submitter_id or actor.id == activity.user_id
    )


def check_actor_can_log_without_mission_validation(actor, mission_user_tuple):
    mission = mission_user_tuple.get("mission")
    user = mission_user_tuple.get("user") or actor
    check_company_id_against_scope(mission.company_id)
    return (
        mission
        and user
        and (actor.id == mission.submitter_id or actor.id == user.id)
    )


def check_actor_can_write_on_mission(actor, mission, for_user=None, at=None):
    check_company_id_against_scope(mission.company_id)
    return check_actor_can_write_on_mission_over_period(
        actor, mission, for_user, start=at, end=at
    )


@dataclass
class ConsultationScope:
    all_access: bool = False
    company_ids: List = field(default_factory=list)
    user_data_min_date: Optional[date] = None
    user_data_max_date: Optional[date] = None


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
            if g.get("company"):
                consultation_scope.company_ids = [g.company.id]
            elif company_further_scoping:
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

            consultation_scope.user_data_min_date = getattr(
                g, "user_data_min_date", None
            )
            consultation_scope.user_data_max_date = getattr(
                g, "user_data_max_date", None
            )

            kwargs["consultation_scope"] = consultation_scope

            return resolver(user, info, *args, **kwargs)

        return wrapper

    return decorator


def controller_can_see_control(controller_user, control_id):
    if not controller_only(controller_user):
        raise AuthorizationError("Accessible only for Controller")
    controller_control = ControllerControl.query.get(control_id)
    if not controller_control:
        raise AuthorizationError("Unknown control id")
    if controller_user.id != controller_control.controller_id:
        raise AuthorizationError("Can not view control of another Controller")
    return True
