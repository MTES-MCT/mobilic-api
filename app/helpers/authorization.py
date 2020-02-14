from flask_jwt_extended import jwt_required, current_user
from graphql import GraphQLError
from inspect import signature
from functools import wraps

from app import app
from app.helpers.authentication import with_auth_error_handling


def allow_all():
    pass


def authenticated(user):
    return user is not None


def admin_only(user):
    return user.admin


def with_authorization_policy(
    authorization_rule,
    get_target_from_args=None,
    get_target_from_return_value=None,
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
        if (
            authorization_rule == allow_all
            or app.config["DISABLE_AUTH_FOR_TESTING"]
        ):
            return resolver

        @wraps(resolver)
        def decorated_resolver(*args, **kwargs):
            if not rule_requires_target and not authorization_rule(
                current_user
            ):
                raise GraphQLError("Unauthorized")
            elif rule_requires_target and get_target_from_args:
                target = get_target_from_args(*args, **kwargs)
                if not authorization_rule(current_user, target):
                    raise GraphQLError("Unauthorized")
            value = resolver(*args, **kwargs)

            if rule_requires_target and get_target_from_return_value:
                target = get_target_from_return_value(value)
                if not authorization_rule(current_user, target):
                    raise GraphQLError("Unauthorized")
            return value

        return with_auth_error_handling(jwt_required(decorated_resolver))

    return decorator
