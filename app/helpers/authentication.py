from calendar import timegm

from flask import g, after_this_request, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    verify_jwt_in_request,
    jwt_refresh_token_required,
    current_user as current_actor,
    get_raw_jwt,
    get_jwt_identity,
    JWTManager,
)
from datetime import date, datetime
import graphene
from flask_jwt_extended.exceptions import (
    JWTExtendedException,
    NoAuthorizationError,
    InvalidHeaderError,
    UserLoadError,
)
from flask_jwt_extended.view_decorators import _decode_jwt_from_headers
from jwt import PyJWTError
from functools import wraps
from werkzeug.local import LocalProxy

from app.controllers.utils import Void

current_user = LocalProxy(lambda: g.get("user") or current_actor)


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

    if not matching_token or matching_token.revoked:
        raise AuthenticationError("Invalid token")

    g.user = matching_token.user


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
    check_impersonate_user()
    if g.get("user"):
        return
    try:
        verify_jwt_in_request()
    except (NoAuthorizationError, InvalidHeaderError):
        raise AuthenticationError(
            "Unable to find a valid cookie or authorization header"
        )
    except UserLoadError:
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
        except (NoAuthorizationError, InvalidHeaderError):
            raise AuthenticationError(
                "Unable to find a valid cookie or authorization header"
            )
        except (JWTExtendedException, PyJWTError):
            raise AuthenticationError("Invalid token")

    return wrapper


@jwt.expired_token_loader
def raise_expired_token_error(token_data):
    raise AuthenticationError(f"Expired {token_data['type']} token")


@jwt.user_loader_callback_loader
def get_user_from_token_identity(identity):
    user = User.query.get(identity["id"])
    if not user:
        return None
    # Check that token is not revoked
    token_issued_at = get_raw_jwt()["iat"]
    if user.latest_token_revocation_time and token_issued_at < int(
        user.latest_token_revocation_time.timestamp()
    ):
        return None
    g.client_id = identity.get("client_id")
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
            expires_delta=False,
        ),
    }
    db.session.commit()
    return tokens


def set_auth_cookies(
    response,
    access_token=None,
    refresh_token=None,
    user_id=None,
    fc_token=None,
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
        "userId",
        value=str(user_id),
        expires=datetime.utcnow() + app.config["SESSION_COOKIE_LIFETIME"],
        secure=app.config["JWT_COOKIE_SECURE"],
        httponly=False,
        samesite="Strict",
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
        samesite="Strict",
    )
    if fc_token:
        response.set_cookie(
            "fct",
            value=fc_token,
            expires=datetime.utcnow() + app.config["SESSION_COOKIE_LIFETIME"],
            secure=app.config["JWT_COOKIE_SECURE"],
            httponly=True,
            path="/api/fc/logout",
            samesite="Strict",
        )
        response.set_cookie(
            "hasFc",
            value="true",
            expires=datetime.utcnow() + app.config["SESSION_COOKIE_LIFETIME"],
            secure=app.config["JWT_COOKIE_SECURE"],
            httponly=False,
            samesite="Strict",
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
    response.delete_cookie("atEat", path="/")


def unset_fc_auth_cookies(response):
    response.delete_cookie("fct", path="/api/fc/logout")
    response.delete_cookie("hasFc", path="/")


class UserTokens(graphene.ObjectType):
    access_token = graphene.String(description="Jeton d'accès")
    refresh_token = graphene.String(description="Jeton de rafraichissement")


class UserTokensWithFC(UserTokens, graphene.ObjectType):
    fc_token = graphene.String(description="Jeton d'accès")


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


class LoginMutation(graphene.Mutation):
    """
    Authentification par email/mot de passe.

    Retourne un jeton d'accès avec une certaine durée de validité et un jeton de rafraichissement
    """

    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info, email, password):
        user = User.query.filter(User.email == email).one_or_none()
        if not user or (
            not app.config["DISABLE_PASSWORD_CHECK"]
            and (not user.password or not user.check_password(password))
        ):
            raise AuthenticationError(
                f"Wrong email/password combination for email {email}"
            )

        tokens = create_access_tokens_for(user)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(response, user_id=user.id, **tokens)
            return response

        return UserTokens(**tokens)


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


class LogoutMutation(graphene.Mutation):
    """
    Invalidation du jeton existant de rafraichissement pour l'utilisateur.

    """

    Output = Void

    @classmethod
    def mutate(cls, _, info):
        logout()
        return Void(success=True)


class RefreshMutation(graphene.Mutation):
    """
    Rafraichissement du jeton d'accès. La requête doit comporter l'en-tête "Authorization: Bearer <JETON_DE_RAFRAICHISSEMENT>"

    Attention, un jeton de rafraichissement ne peut être utilisé qu'une seule fois

    Retourne un nouveau jeton d'accès et un nouveau jeton de rafraichissement
    """

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info):
        return UserTokens(**_refresh_token())


class Auth(graphene.ObjectType):
    """
    Authentification
    """

    login = LoginMutation.Field()
    refresh = RefreshMutation.Field()
    logout = LogoutMutation.Field()


@wrap_jwt_errors
def _refresh_token():
    delete_refresh_token()
    tokens = create_access_tokens_for(
        current_actor, client_id=g.get("client_id")
    )

    @after_this_request
    def set_cookies(response):
        set_auth_cookies(response, user_id=current_actor.id, **tokens)
        return response

    return tokens


@app.route("/token/refresh", methods=["POST"])
def rest_refresh_token():
    try:
        tokens = _refresh_token()
        return jsonify(tokens), 200
    except AuthenticationError as e:

        @after_this_request
        def unset_cookies(response):
            unset_auth_cookies(response)
            return response

        raise


@wrap_jwt_errors
def logout():
    delete_refresh_token()
    db.session.commit()


@app.route("/token/logout", methods=["POST"])
def rest_logout():
    @after_this_request
    def unset_cookies(response):
        unset_auth_cookies(response)
        return response

    logout()
    return jsonify({"success": True}), 200


@jwt_refresh_token_required
def delete_refresh_token():
    from app.models.refresh_token import RefreshToken

    identity = get_jwt_identity()
    matching_refresh_token = RefreshToken.get_token(
        token=identity.get("token"), user_id=identity.get("id")
    )
    if not matching_refresh_token:
        raise AuthenticationError("Refresh token is invalid")
    db.session.delete(matching_refresh_token)
