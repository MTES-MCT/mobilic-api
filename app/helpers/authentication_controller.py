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
    refresh_token_string=None,
):
    from app.models import ControllerRefreshToken

    if refresh_token_string is None:
        refresh_token_string = (
            ControllerRefreshToken.create_controller_refresh_token(
                controller_user
            )
        )

    tokens = {
        "access_token": create_access_token(
            {"controllerUserId": controller_user.id, "controller": True},
            expires_delta=app.config["ACCESS_TOKEN_EXPIRATION"],
        ),
        "refresh_token": create_refresh_token(
            {
                "controllerUserId": controller_user.id,
                "token": refresh_token_string,
                "controller": True,
            },
            expires_delta=app.config["REFRESH_TOKEN_EXPIRATION"],
        ),
    }
    db.session.commit()
    return tokens


def _issue_controller_tokens_and_set_cookies(
    controller_user, refresh_token_string
):
    tokens = create_access_tokens_for_controller(
        controller_user, refresh_token_string=refresh_token_string
    )

    @after_this_request
    def set_cookies(response):
        set_controller_auth_cookies(
            response, controller_user_id=controller_user.id, **tokens
        )
        return response

    return tokens


@wrap_jwt_errors
@jwt_required(refresh=True)
def refresh_controller_token():
    from app.models import ControllerRefreshToken
    from app.helpers.authentication import (
        get_replayable_consumed_token,
        unset_auth_cookies,
    )

    try:
        identity = get_jwt_identity()
        controller_user_id = identity.get("controllerUserId")
        token_string = identity.get("token")

        consumed_token = ControllerRefreshToken.consume(
            token_string, controller_user_id
        )

        if consumed_token is None:
            successor = get_replayable_consumed_token(
                ControllerRefreshToken,
                token_string,
                controller_user_id,
                "controller",
            )
            return _issue_controller_tokens_and_set_cookies(
                current_actor, successor.token
            )

        if (
            consumed_token.creation_time
            < datetime.now(tz=timezone.utc).replace(tzinfo=None)
            - app.config["REFRESH_TOKEN_EXPIRATION"]
        ):
            app.logger.info(
                f"Expired refresh token for controller {controller_user_id}"
            )
            raise AuthenticationError("Refresh token has expired")

        successor_token_string = (
            ControllerRefreshToken.create_controller_refresh_token(
                current_actor
            )
        )
        consumed_token.replaced_by_token = successor_token_string

        return _issue_controller_tokens_and_set_cookies(
            current_actor, successor_token_string
        )

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
    from app.helpers.authentication import find_live_successor

    identity = get_jwt_identity()
    controller_user_id = identity.get("controllerUserId")

    matching_refresh_token = ControllerRefreshToken.get_token(
        token=identity.get("token"), controller_user_id=controller_user_id
    )

    if matching_refresh_token:
        if matching_refresh_token.consumed_at is not None:
            live_successor = find_live_successor(
                ControllerRefreshToken,
                matching_refresh_token,
                controller_user_id,
            )
            if live_successor is not None:
                db.session.delete(live_successor)
                app.logger.info(
                    f"Live successor {live_successor.token} deleted for controller {controller_user_id} at logout"
                )
        db.session.delete(matching_refresh_token)
        app.logger.info(
            f"Matching controller refresh token {identity.get('token')} deleted for controller {controller_user_id}"
        )
    else:
        app.logger.info(
            f"No matching refresh token found for controller {controller_user_id} at logout"
        )

    app.logger.info(
        f"Completed token cleanup for controller {controller_user_id}"
    )
