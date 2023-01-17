from inspect import signature
from functools import wraps

from flask import g

from app.helpers.api_key_authentication import require_api_key_decorator
from app.helpers.authentication import current_user, require_auth
from app.helpers.errors import AuthorizationError
from app.models import ControllerUser


def active(user):
    if not user:
        return False
    if not user.has_activated_email:
        raise AuthorizationError(
            "Actor is not active. The email activation is required to perform mutations."
        )
    return True


def admin_only(user):
    return user.admin


def controller_only(controller_user):
    return isinstance(controller_user, ControllerUser)


def with_protected_authorization_policy(
    authorization_rule,
    get_target_from_args=None,
    error_message="Forbidden operation",
):
    rule_requires_target = len(signature(authorization_rule).parameters) > 0
    if rule_requires_target and get_target_from_args is None:
        raise ValueError(
            f"The authorization rule {authorization_rule} needs a target to be applied to. "
            f"You must set exactly get_target_from_args"
        )

    def decorator(resolver):
        @wraps(resolver)
        def decorated_resolver(*args, **kwargs):
            if not rule_requires_target and not authorization_rule():
                raise AuthorizationError(error_message)
            elif rule_requires_target and get_target_from_args:
                try:
                    target = get_target_from_args(*args, **kwargs)
                except:
                    raise AuthorizationError(error_message)
                if not authorization_rule(target):
                    raise AuthorizationError(error_message)

            return resolver(*args, **kwargs)

        return require_api_key_decorator(decorated_resolver)

    return decorator


def with_authorization_policy(
    authorization_rule,
    get_target_from_args=None,
    get_target_from_return_value=None,
    error_message="Forbidden operation",
):
    rule_requires_target = len(signature(authorization_rule).parameters) > 1
    if rule_requires_target and (
        (get_target_from_args is None)
        == (get_target_from_return_value is None)
    ):
        raise ValueError(
            f"The authorization rule {authorization_rule} needs a target to be applied to. "
            f"You must set exactly one of get_target_from_args or get_target_from_return_value"
        )

    def decorator(resolver):
        @wraps(resolver)
        def decorated_resolver(*args, **kwargs):
            if not rule_requires_target and not authorization_rule(
                current_user
            ):
                raise AuthorizationError(error_message)
            elif rule_requires_target and get_target_from_args:
                try:
                    target = get_target_from_args(*args, **kwargs)
                except:
                    raise AuthorizationError(error_message)
                if not authorization_rule(current_user, target):
                    raise AuthorizationError(error_message)

            value = resolver(*args, **kwargs)

            if rule_requires_target and get_target_from_return_value:
                target = get_target_from_return_value(value)
                if not authorization_rule(current_user, target):
                    raise AuthorizationError(error_message)
            return value

        return require_auth(decorated_resolver)

    return decorator


def check_company_against_scope_wrapper(company_id_resolver):
    def decorator(resolver):
        @wraps(resolver)
        def decorated_resolver(*args, **kwargs):
            company_id = company_id_resolver(*args, **kwargs)
            check_company_id_against_scope(company_id)
            return resolver(*args, **kwargs)

        return decorated_resolver

    return decorator


def check_company_id_against_scope(company_id):
    if g.get("company") and g.company.id != company_id:
        raise AuthorizationError(
            "Actor is not authorized to perform the operation"
        )


def check_company_ids_against_scope(company_ids):
    if g.get("company") and (
        len(company_ids) > 1 or g.company.id != company_ids[0]
    ):
        raise AuthorizationError(
            "Actor is not authorized to perform the operation"
        )
