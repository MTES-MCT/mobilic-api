from calendar import timegm
from datetime import datetime, timezone

import graphene
from flask import after_this_request, g, request

from app import app
from app.controllers.utils import Void
from app.domain.impersonation import (
    IMPERSONATION_EXPIRATION,
    create_impersonation_token,
    get_admin_token_from_cookie,
    validate_impersonation_prerequisites,
)
from app.helpers.authentication import (
    AuthenticatedMutation,
    current_user,
)
from app.helpers.authorization import (
    admin_only,
    with_authorization_policy,
)
from app.helpers.errors import AuthorizationError


def _set_impersonation_access_cookie(
    response, token, user_id, expires_delta=None
):
    response.set_cookie(
        app.config["JWT_ACCESS_COOKIE_NAME"],
        value=token,
        httponly=True,
        secure=app.config["JWT_COOKIE_SECURE"],
        path=app.config["JWT_ACCESS_COOKIE_PATH"],
        samesite="Strict",
    )
    response.set_cookie(
        "userId",
        value=str(user_id),
        secure=app.config["JWT_COOKIE_SECURE"],
    )
    if expires_delta:
        expiry = datetime.now(timezone.utc) + expires_delta
        response.set_cookie(
            "atEat",
            value=str(timegm(expiry.utctimetuple())),
            secure=app.config["JWT_COOKIE_SECURE"],
        )


class StartImpersonationOutput(graphene.ObjectType):
    access_token = graphene.String(required=True)
    impersonated_user_id = graphene.Int(required=True)


class StartImpersonation(AuthenticatedMutation):
    class Arguments:
        user_id = graphene.Int(
            required=True,
            description="ID de l'utilisateur à impersonner",
        )

    Output = StartImpersonationOutput

    @classmethod
    @with_authorization_policy(admin_only)
    def mutate(cls, _, info, user_id):
        validate_impersonation_prerequisites(current_user)
        result = create_impersonation_token(current_user, user_id)

        current_admin_token = request.cookies.get(
            app.config["JWT_ACCESS_COOKIE_NAME"]
        )

        @after_this_request
        def set_cookies(response):
            if current_admin_token:
                response.set_cookie(
                    "admin_token",
                    value=current_admin_token,
                    httponly=True,
                    secure=app.config["JWT_COOKIE_SECURE"],
                    samesite="Lax",
                    path="/",
                )
            _set_impersonation_access_cookie(
                response,
                result["access_token"],
                result["impersonated_user_id"],
                expires_delta=IMPERSONATION_EXPIRATION,
            )
            return response

        return StartImpersonationOutput(**result)


class StopImpersonation(AuthenticatedMutation):
    class Arguments:
        pass

    Output = Void

    @classmethod
    def mutate(cls, _, info):
        impersonate_by = getattr(g, "impersonate_by", None)
        if not impersonate_by:
            raise AuthorizationError("Not in impersonation session")
        admin_token = get_admin_token_from_cookie()

        @after_this_request
        def restore_cookies(response):
            _set_impersonation_access_cookie(
                response, admin_token, impersonate_by
            )
            response.delete_cookie("admin_token", path="/")
            return response

        return Void(success=True)
