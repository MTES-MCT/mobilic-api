from flask import g, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    jwt_optional,
    jwt_refresh_token_required,
    current_user as current_actor,
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
    if not user or not user.refresh_token_nonce:
        return None
    nonce = identity.get("nonce")
    # Specific refresh token check
    if nonce and nonce != user.refresh_token_nonce:
        return None
    return user


def create_access_tokens_for(user):
    new_refresh_nonce = user.generate_refresh_token_nonce()
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
            },
            expires_delta=app.config["ACCESS_TOKEN_EXPIRATION"],
        ),
        "refresh_token": create_refresh_token(
            {"id": user.id, "nonce": new_refresh_nonce}, expires_delta=False
        ),
    }
    db.session.commit()
    return tokens


class UserTokens(graphene.ObjectType):
    access_token = graphene.String(description="Jeton d'accès")
    refresh_token = graphene.String(description="Jeton de rafraichissement")


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
        if not user or not user.check_password(password):
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
    Invalidation de tous les jetons existants pour l'utilisateur.

    """

    message = graphene.String()

    @classmethod
    @with_auth_error_handling
    @jwt_required
    def mutate(cls, _, info):
        current_actor.refresh_token_nonce = None
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
        return UserTokens(**create_access_tokens_for(current_actor))


class Auth(graphene.ObjectType):
    """
    Authentification
    """

    login = LoginMutation.Field()
    refresh = RefreshMutation.Field()
    check = CheckMutation.Field()
    logout = LogoutMutation.Field()
