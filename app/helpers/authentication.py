from calendar import timegm
from datetime import datetime, timezone
from functools import wraps

import graphene
from flask import g, after_this_request, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    verify_jwt_in_request,
    current_user as current_actor,
    get_jwt_identity,
    JWTManager,
)
from flask_jwt_extended.exceptions import (
    JWTExtendedException,
    NoAuthorizationError,
    InvalidHeaderError,
    UserLookupError,
)
from flask_jwt_extended.view_decorators import (
    _decode_jwt_from_headers,
    jwt_required,
)
from jwt import PyJWTError
from werkzeug.local import LocalProxy

CLIENT_ID_HTTP_HEADER_NAME = "X-CLIENT-ID"
EMPLOYMENT_TOKEN_HTTP_HEADER_NAME = "X-EMPLOYMENT-TOKEN"


def current_flask_user():
    try:
        verify_jwt_in_request()
    except:
        return None
    return current_actor


current_user = LocalProxy(lambda: g.get("user") or current_flask_user())

from app.models.controller_user import ControllerUser
from app.models.user import User
from app import app, db
from app.helpers.errors import AuthenticationError, AuthorizationError

jwt = JWTManager(app)


def verify_oauth_token_in_request():
    from app.helpers.oauth import OAuth2Token

    # We use the internal function from flask-jwt-extended to extract the token part in the authorization header
    # rather than reimplementing our own
    oauth_token_string, _ = _decode_jwt_from_headers()
    matching_token = OAuth2Token.query.filter(
        OAuth2Token.token == oauth_token_string
    ).one_or_none()

    if not matching_token or matching_token.is_revoked:
        app.logger.info(f"Invalid oauth token")
        raise AuthenticationError("Invalid token")

    g.user = matching_token.user


def check_employment_token():
    from app.helpers.oauth.models import ThirdPartyClientEmployment
    from app.helpers.api_key_authentication import (
        check_protected_client_id_company_id,
    )

    client_id = request.headers.get(CLIENT_ID_HTTP_HEADER_NAME)
    token = request.headers.get(EMPLOYMENT_TOKEN_HTTP_HEADER_NAME)
    if not client_id or not token:
        return

    if not client_id.isnumeric():
        app.logger.info(f"Invalid {CLIENT_ID_HTTP_HEADER_NAME}")
        raise AuthenticationError("Invalid token")

    matching_token = ThirdPartyClientEmployment.query.filter(
        ThirdPartyClientEmployment.client_id == client_id,
        ThirdPartyClientEmployment.access_token == token,
        ~ThirdPartyClientEmployment.is_dismissed,
    ).one_or_none()
    if not matching_token:
        app.logger.info(f"Invalid {EMPLOYMENT_TOKEN_HTTP_HEADER_NAME}")
        raise AuthenticationError("Invalid token")

    if not check_protected_client_id_company_id(
        matching_token.employment.company_id
    ):
        raise AuthenticationError("Company token has been revoked")

    g.user = matching_token.employment.user
    g.company = matching_token.employment.company


def check_impersonate_user():
    from app.models import UserReadToken

    impersonation_token = request.headers.get("Impersonation-Token")
    if impersonation_token:
        existing_token = UserReadToken.get_token(impersonation_token)
        g.user = existing_token.user
        g.user_data_max_date = existing_token.creation_day
        g.user_data_min_date = existing_token.history_start_day
        g.read_only_access = True


def check_auth():
    if current_user:
        return
    check_employment_token()
    check_impersonate_user()
    if g.get("user"):
        return
    try:
        verify_jwt_in_request()
    except (NoAuthorizationError, InvalidHeaderError) as e:
        app.logger.info(f"Authorization error: {str(e)}")
        raise AuthenticationError(
            "Unable to find a valid cookie or authorization header"
        )
    except UserLookupError as e:
        app.logger.info(f"User lookup error: {str(e)}")
        raise AuthenticationError("Invalid token")
    except (JWTExtendedException, PyJWTError):
        verify_oauth_token_in_request()


def _auth_decorator(required=True):
    def decorator(f=lambda *args, **kwargs: None):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                check_auth()
            except:
                if required:
                    raise
            return f(*args, **kwargs)

        return wrapper

    return decorator


require_auth = _auth_decorator(required=True)
optional_auth = _auth_decorator(required=False)


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


@jwt.expired_token_loader
def raise_expired_token_error(jwt_header, jwt_payload):
    raise AuthenticationError(f"Expired {jwt_payload['type']} token")


@jwt.user_lookup_loader
def get_user_from_token_identity(jwt_header, jwt_payload):
    if jwt_payload["identity"].get("controller"):
        controller_user = ControllerUser.query.get(
            jwt_payload["identity"]["controllerUserId"]
        )
        return controller_user
    user = User.query.get(jwt_payload["identity"]["id"])
    if not user:
        return None
    # Check that token is not revoked
    token_issued_at = jwt_payload["iat"]
    if user.latest_token_revocation_time and token_issued_at < int(
        user.latest_token_revocation_time.timestamp()
    ):
        return None
    g.client_id = jwt_payload["identity"].get("client_id")
    return user


def create_access_tokens_for(
    user,
    client_id=None,
):
    from app.models.refresh_token import RefreshToken

    tokens = {
        "access_token": create_access_token(
            {
                "id": user.id,
                "client_id": client_id,
            },
            expires_delta=app.config["ACCESS_TOKEN_EXPIRATION"],
        ),
        "refresh_token": create_refresh_token(
            {
                "id": user.id,
                "token": RefreshToken.create_refresh_token(user),
                "client_id": client_id,
            },
            expires_delta=None,
        ),
    }
    db.session.commit()
    return tokens


def set_auth_cookies_helper(
    response,
    access_token=None,
    refresh_token=None,
    user_id=None,
    controller_user_id=None,
    fc_token=None,
    ac_token=None,
):
    """
    Set authentication cookies on response.

    Args:
        response: Flask response object
        access_token: JWT access token
        refresh_token: JWT refresh token
        user_id: User ID (for regular users)
        controller_user_id: Controller user ID (for controller users)
        fc_token: FranceConnect token
        ac_token: AgentConnect token
    """
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

    # Cookies auth (access and refresh tokens)
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

    # Token expiration time cookie
    set_cookie_with_defaults(
        "atEat",
        str(timegm(access_token_expires.utctimetuple())),
        httponly=False,
    )

    # User identification cookies
    if user_id is not None:
        set_cookie_with_defaults("userId", str(user_id), httponly=False)

    if controller_user_id is not None:
        set_cookie_with_defaults(
            "controllerId", str(controller_user_id), httponly=False
        )

    # FranceConnect cookies
    if fc_token:
        set_cookie_with_defaults(
            "fct",
            fc_token,
            httponly=True,
            path="/api/fc/logout",
            samesite="Strict",
        )
        set_cookie_with_defaults("hasFc", "true", httponly=False)

    # AgentConnect cookies
    if ac_token:
        set_cookie_with_defaults(
            "act",
            ac_token,
            httponly=True,
            path="/api/ac/logout",
            samesite="Strict",
        )
        set_cookie_with_defaults("hasAc", "true", httponly=False)


def set_auth_cookies(
    response,
    access_token=None,
    refresh_token=None,
    user_id=None,
    fc_token=None,
    ac_token=None,
):
    """Set authentication cookies for regular users."""
    return set_auth_cookies_helper(
        response=response,
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        fc_token=fc_token,
        ac_token=ac_token,
    )


def unset_auth_cookies(response):
    response.delete_cookie(
        app.config["JWT_ACCESS_COOKIE_NAME"],
        path=app.config["JWT_ACCESS_COOKIE_PATH"],
    )
    response.delete_cookie(
        app.config["JWT_REFRESH_COOKIE_NAME"],
        path=app.config["JWT_REFRESH_COOKIE_PATH"],
    )
    response.delete_cookie("userId", path="/")
    response.delete_cookie("controllerId", path="/")
    response.delete_cookie("atEat", path="/")


def unset_fc_auth_cookies(response):
    response.delete_cookie("fct", path="/api/fc/logout")
    response.delete_cookie("hasFc", path="/")


def unset_ac_auth_cookies(response):
    response.delete_cookie("act", path="/api/ac/logout")
    response.delete_cookie("hasAc", path="/")


class UserTokens(graphene.ObjectType):
    access_token = graphene.String(description="Jeton d'accès")
    refresh_token = graphene.String(description="Jeton de rafraichissement")


class UserTokensWithFC(UserTokens, graphene.ObjectType):
    fc_token = graphene.String(description="Jeton d'accès")


class UserTokensWithAC(UserTokens, graphene.ObjectType):
    ac_token = graphene.String(description="Jeton d'accès")


def require_auth_with_write_access(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.get("read_only_access", False):
            raise AuthorizationError(
                "Mutations are not allowed in read access mode"
            )
        return f(*args, **kwargs)

    return require_auth(wrapper)


class AuthenticatedMutation(graphene.Mutation, abstract=True):
    @classmethod
    def __init_subclass__(cls, **kwargs):
        cls.mutate = require_auth_with_write_access(cls.mutate)
        super(AuthenticatedMutation, cls).__init_subclass__(**kwargs)


class CheckOutput(graphene.ObjectType):
    success = graphene.Boolean()
    user_id = graphene.Int()


class CheckQuery(graphene.ObjectType):
    """
    Test de validité du jeton d'accès.

    """

    check_auth = graphene.Field(CheckOutput, required=True)

    @require_auth
    def resolve_check_auth(self, info):
        return CheckOutput(success=True, user_id=current_user.id)


@wrap_jwt_errors
@jwt_required(refresh=True)
def refresh_token():
    from app.models.refresh_token import RefreshToken

    try:
        identity = get_jwt_identity()
        matching_token = RefreshToken.get_token(
            token=identity.get("token"), user_id=identity.get("id")
        )
        if not matching_token:
            app.logger.error(
                f"Invalid refresh token for user {identity.get('id')}. Token not found in database."
            )
            raise AuthenticationError("Refresh token is invalid")

        tokens = create_access_tokens_for(
            current_actor, client_id=g.get("client_id")
        )

        db.session.delete(matching_token)
        db.session.commit()

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(response, user_id=current_actor.id, **tokens)
            return response

        return tokens

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Token refresh error: {str(e)}")

        @after_this_request
        def clear_cookies(response):
            unset_auth_cookies(response)
            return response

        raise


@wrap_jwt_errors
def logout():
    try:
        delete_refresh_token()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Logout error: {str(e)}")

        @after_this_request
        def clear_cookies(response):
            unset_auth_cookies(response)
            return response

        raise


@jwt_required(refresh=True)
def delete_refresh_token():
    from app.models.refresh_token import RefreshToken
    from app.helpers.authentication_controller import (
        delete_controller_refresh_token,
    )

    identity = get_jwt_identity()
    if identity.get("controller"):
        delete_controller_refresh_token()
    else:
        user_id = identity.get("id")
        matching_refresh_token = RefreshToken.get_token(
            token=identity.get("token"),
            user_id=user_id,
        )

        if matching_refresh_token:
            db.session.delete(matching_refresh_token)
            app.logger.info(
                f"Matching refresh token {identity.get('token')} deleted for user {user_id}"
            )
        else:
            refresh_tokens = RefreshToken.query.filter_by(
                user_id=user_id
            ).all()

            app.logger.warning(
                f"No matching refresh token found. Deleting all {len(refresh_tokens)} tokens for user {user_id}"
            )

            for token in refresh_tokens:
                db.session.delete(token)

        app.logger.info(f"Completed token cleanup for user {user_id}")
