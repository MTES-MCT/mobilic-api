from flask import g, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    jwt_optional,
    jwt_refresh_token_required,
    current_user as current_actor,
    get_raw_jwt,
    get_jwt_identity,
    decode_token,
    JWTManager,
)
from datetime import date
import graphene
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt import PyJWTError
from functools import wraps
from werkzeug.local import LocalProxy

current_user = LocalProxy(lambda: g.get("as_user") or current_actor)

from app.models.user import User
from app import app, db
from app.helpers.errors import AuthenticationError

jwt = JWTManager(app)


def user_loader(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if app.config["ALLOW_INSECURE_IMPERSONATION"] and not g.get("as_user"):
            as_user_id = request.args.get("_as_user")
            if as_user_id:
                try:
                    as_user_id = int(as_user_id)
                    g.as_user = User.query.get(as_user_id)
                except:
                    pass
        if g.get("as_user"):
            return jwt_optional(f)(*args, **kwargs)
        return jwt_required(f)(*args, **kwargs)

    return wrapper


def with_auth_error_handling(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (JWTExtendedException, PyJWTError) as e:
            raise AuthenticationError("Error during token validation")

    return wrapper


@jwt.user_loader_callback_loader
def get_user_from_token_identity(identity):
    user = User.query.get(identity["id"])
    if not user:
        return None
    # Check that token is not revoked
    token_issued_at = get_raw_jwt()["iat"]
    if (
        user.latest_token_revocation_time
        and token_issued_at <= user.latest_token_revocation_time.timestamp()
    ):
        return None
    g.client_id = identity.get("client_id")
    return user


def create_access_tokens_for(
    user,
    client_id=None,
    include_refresh_token=True,
    include_additional_info=False,
):
    from app.models.refresh_token import RefreshToken

    current_primary_employment = user.primary_employment_at(date.today())
    tokens = {
        "access_token": create_access_token(
            {
                "id": user.id,
                "company_id": current_primary_employment.company_id
                if current_primary_employment
                else None,
                "company_admin": current_primary_employment.has_admin_rights
                if current_primary_employment
                else None,
                "client_id": client_id,
            },
            expires_delta=app.config["ACCESS_TOKEN_EXPIRATION"],
        )
    }
    if include_additional_info:
        tokens.update(
            {
                "token_type": "Bearer",
                "expires_in": round(
                    app.config["ACCESS_TOKEN_EXPIRATION"].total_seconds()
                ),
            }
        )
    if include_refresh_token:
        tokens["refresh_token"] = create_refresh_token(
            {
                "id": user.id,
                "token": RefreshToken.create_refresh_token(user),
                "client_id": client_id,
            },
            expires_delta=False,
        )
    db.session.commit()
    return tokens


class UserTokens(graphene.ObjectType):
    access_token = graphene.String(description="Jeton d'accès")
    refresh_token = graphene.String(description="Jeton de rafraichissement")


class UserTokensWithFC(UserTokens, graphene.ObjectType):
    fc_token = graphene.String(description="Jeton d'accès")


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
    @with_auth_error_handling
    def mutate(cls, _, info, email, password):
        app.logger.info(f"{email} is attempting to log in")
        user = User.query.filter(User.email == email).one_or_none()
        if not user or not user.password or not user.check_password(password):
            raise AuthenticationError(
                f"Wrong email/password combination for email {email}"
            )
        return UserTokens(**create_access_tokens_for(user))


class CheckMutation(graphene.Mutation):
    """
    Test de validité du jeton d'accès.

    """

    message = graphene.String()
    user_id = graphene.Int()

    @classmethod
    @with_auth_error_handling
    @jwt_required
    def mutate(cls, _, info):
        return CheckMutation(message="success", user_id=current_actor.id)


class LogoutMutation(graphene.Mutation):
    """
    Invalidation du jeton existant de rafraichissement pour l'utilisateur.

    """

    class Arguments:
        refresh_token = graphene.Argument(
            graphene.String,
            required=True,
            description="Le jeton de rafraichissement à invalider",
        )

    message = graphene.String()

    @classmethod
    @with_auth_error_handling
    @jwt_required
    def mutate(cls, _, info, refresh_token):
        from app.models.refresh_token import RefreshToken

        try:
            decoded_refresh_token = decode_token(refresh_token)
            identity = decoded_refresh_token["identity"]
            matching_refresh_token = RefreshToken.get_token(
                token=identity["token"], user_id=identity["id"]
            )
            db.session.delete(matching_refresh_token)
        except Exception as e:
            pass
        db.session.commit()
        return LogoutMutation(message="success")


class RefreshMutation(graphene.Mutation):
    """
    Rafraichissement du jeton d'accès. La requête doit comporter l'en-tête "Authorization: Bearer <JETON_DE_RAFRAICHISSEMENT>"

    Attention, un jeton de rafraichissement ne peut être utilisé qu'une seule fois

    Retourne un nouveau jeton d'accès et un nouveau jeton de rafraichissement
    """

    Output = UserTokens

    @classmethod
    @with_auth_error_handling
    @jwt_refresh_token_required
    def mutate(cls, _, info):
        from app.models.refresh_token import RefreshToken

        identity = get_jwt_identity()
        matching_refresh_token = RefreshToken.get_token(
            token=identity["token"], user_id=identity["id"]
        )
        if not matching_refresh_token:
            raise AuthenticationError("Refresh token is invalid")
        db.session.delete(matching_refresh_token)

        return UserTokens(
            **create_access_tokens_for(
                current_actor, client_id=g.get("client_id")
            )
        )


class Auth(graphene.ObjectType):
    """
    Authentification
    """

    login = LoginMutation.Field()
    refresh = RefreshMutation.Field()
    check = CheckMutation.Field()
    logout = LogoutMutation.Field()
