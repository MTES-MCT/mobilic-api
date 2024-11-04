from calendar import timegm
from datetime import datetime
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
    response.set_cookie(
        app.config["JWT_ACCESS_COOKIE_NAME"],
        value=access_token,
        expires=datetime.utcnow() + app.config["ACCESS_TOKEN_EXPIRATION"],
        secure=app.config["JWT_COOKIE_SECURE"],
        httponly=True,
        path=app.config["JWT_ACCESS_COOKIE_PATH"],
        samesite="Strict",
    )
    response.set_cookie(
        app.config["JWT_REFRESH_COOKIE_NAME"],
        value=refresh_token,
        expires=datetime.utcnow() + app.config["SESSION_COOKIE_LIFETIME"],
        secure=app.config["JWT_COOKIE_SECURE"],
        httponly=True,
        path=app.config["JWT_REFRESH_COOKIE_PATH"],
        samesite="Strict",
    )
    response.set_cookie(
        "controllerId",
        value=str(controller_user_id),
        expires=datetime.utcnow() + app.config["SESSION_COOKIE_LIFETIME"],
        secure=app.config["JWT_COOKIE_SECURE"],
        httponly=False,
    )
    response.set_cookie(
        "atEat",
        value=str(
            timegm(
                (
                    datetime.utcnow() + app.config["ACCESS_TOKEN_EXPIRATION"]
                ).utctimetuple()
            )
        ),
        expires=datetime.utcnow() + app.config["SESSION_COOKIE_LIFETIME"],
        secure=app.config["JWT_COOKIE_SECURE"],
        httponly=False,
    )
    if ac_token:
        response.set_cookie(
            "act",
            value=ac_token,
            expires=datetime.utcnow() + app.config["SESSION_COOKIE_LIFETIME"],
            secure=app.config["JWT_COOKIE_SECURE"],
            httponly=True,
            path="/api/ac/logout",
            samesite="Strict",
        )
    response.set_cookie(
        "hasAc",
        value="true",
        expires=datetime.utcnow() + app.config["SESSION_COOKIE_LIFETIME"],
        secure=app.config["JWT_COOKIE_SECURE"],
        httponly=False,
    )


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
    delete_controller_refresh_token()
    tokens = create_access_tokens_for_controller(current_actor)

    @after_this_request
    def set_cookies(response):
        set_controller_auth_cookies(
            response, controller_user_id=current_actor.id, **tokens
        )
        return response

    return tokens


@jwt_required(refresh=True)
def delete_controller_refresh_token():
    from app.models.controller_refresh_token import ControllerRefreshToken

    identity = get_jwt_identity()
    matching_refresh_token = ControllerRefreshToken.get_token(
        token=identity.get("token"),
        controller_user_id=identity.get("controllerUserId"),
    )
    if not matching_refresh_token:
        raise AuthenticationError("Refresh token is invalid")
    db.session.delete(matching_refresh_token)
