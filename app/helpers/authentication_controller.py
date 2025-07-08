from calendar import timegm
from datetime import datetime, timezone
from functools import wraps

from flask import after_this_request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    current_user as current_actor,
    jwt_required,
)
from flask_jwt_extended.exceptions import (
    NoAuthorizationError,
    InvalidHeaderError,
    JWTExtendedException,
)
from jwt import PyJWTError

from app import app, db
from app.helpers.errors import AuthenticationError


def wrap_jwt_errors(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (NoAuthorizationError, InvalidHeaderError) as e:
            app.logger.info(f"Authorization error: {str(e)}")
            raise AuthenticationError(
                "Unable to find a valid cookie or authorization header"
            )
        except (JWTExtendedException, PyJWTError) as e:
            app.logger.info(f"JWT error: {str(e)}")
            raise AuthenticationError("Invalid token")

    return wrapper


def set_controller_auth_cookies(
    response,
    access_token,
    refresh_token,
    controller_user_id,
    ac_token=None,
):
    # Cookie expiration times
    now = datetime.now(timezone.utc)
    access_token_expires = now + app.config["ACCESS_TOKEN_EXPIRATION"]
    session_expires = now + app.config["SESSION_COOKIE_LIFETIME"]

    # Cookies common parameters
    common_cookie_params = {
        "secure": app.config["JWT_COOKIE_SECURE"],
        "expires": session_expires,
    }

    # Cookies helper
    def set_cookie_with_defaults(name, value, **extra_params):
        params = common_cookie_params.copy()
        params.update(extra_params)
        response.set_cookie(name, value=value, **params)

    # Cookies auth
    set_cookie_with_defaults(
        app.config["JWT_ACCESS_COOKIE_NAME"],
        access_token,
        expires=access_token_expires,
        httponly=True,
        path=app.config["JWT_ACCESS_COOKIE_PATH"],
        samesite="Strict",
    )

    set_cookie_with_defaults(
        app.config["JWT_REFRESH_COOKIE_NAME"],
        refresh_token,
        httponly=True,
        path=app.config["JWT_REFRESH_COOKIE_PATH"],
        samesite="Strict",
    )

    # Cookies controller
    set_cookie_with_defaults(
        "controllerId", str(controller_user_id), httponly=False
    )

    set_cookie_with_defaults(
        "atEat",
        str(timegm(access_token_expires.utctimetuple())),
        httponly=False,
    )

    # Cookies AgentConnect
    if ac_token:
        set_cookie_with_defaults(
            "act",
            ac_token,
            httponly=True,
            path="/api/ac/logout",
            samesite="Strict",
        )

    set_cookie_with_defaults("hasAc", "true", httponly=False)


def create_access_tokens_for_controller(
    controller_user,
):
    from app.models import ControllerRefreshToken

    tokens = {
        "access_token": create_access_token(
            {"controllerUserId": controller_user.id, "controller": True},
            expires_delta=app.config["ACCESS_TOKEN_EXPIRATION"],
        ),
        "refresh_token": create_refresh_token(
            {
                "controllerUserId": controller_user.id,
                "token": ControllerRefreshToken.create_controller_refresh_token(
                    controller_user
                ),
                "controller": True,
            },
            expires_delta=None,
        ),
    }
    db.session.commit()
    return tokens


@wrap_jwt_errors
@jwt_required(refresh=True)
def refresh_controller_token():
    from app.models import ControllerRefreshToken
    from app.helpers.authentication import unset_auth_cookies

    try:
        identity = get_jwt_identity()
        matching_token = ControllerRefreshToken.get_token(
            token=identity.get("token"),
            controller_user_id=identity.get("controllerUserId"),
        )
        if not matching_token:
            app.logger.error(
                f"Invalid refresh token for controller {identity.get('controllerUserId')}. Token not found in database."
            )
            raise AuthenticationError("Refresh token is invalid")

        tokens = create_access_tokens_for_controller(current_actor)

        db.session.delete(matching_token)
        db.session.commit()

        @after_this_request
        def set_cookies(response):
            set_controller_auth_cookies(
                response, controller_user_id=current_actor.id, **tokens
            )
            return response

        return tokens

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Controller token refresh error: {str(e)}")

        @after_this_request
        def clear_cookies(response):
            unset_auth_cookies(response)
            return response

        raise


@jwt_required(refresh=True)
def delete_controller_refresh_token():
    from app.models import ControllerRefreshToken

    identity = get_jwt_identity()
    controller_user_id = identity.get("controllerUserId")

    matching_refresh_token = ControllerRefreshToken.get_token(
        token=identity.get("token"), controller_user_id=controller_user_id
    )

    if matching_refresh_token:
        db.session.delete(matching_refresh_token)
        app.logger.info(
            f"Matching controller refresh token {identity.get('token')} deleted for controller {controller_user_id}"
        )
    else:
        refresh_tokens = ControllerRefreshToken.query.filter_by(
            controller_user_id=controller_user_id
        ).all()

        app.logger.warning(
            f"No matching refresh token found. Deleting all {len(refresh_tokens)} tokens for controller {controller_user_id}"
        )

        for token in refresh_tokens:
            db.session.delete(token)

    app.logger.info(
        f"Completed token cleanup for controller {controller_user_id}"
    )
