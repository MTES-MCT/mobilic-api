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
from app.helpers.authentication import set_auth_cookies_helper


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
    """Set authentication cookies for controller users."""
    return set_auth_cookies_helper(
        response=response,
        access_token=access_token,
        refresh_token=refresh_token,
        controller_user_id=controller_user_id,
        ac_token=ac_token,
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
