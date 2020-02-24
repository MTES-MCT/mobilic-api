from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    jwt_refresh_token_required,
    current_user,
    JWTManager,
)
import graphene
from graphql import GraphQLError
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt import PyJWTError
from functools import wraps

from app.models.user import User
from app import app, db

jwt = JWTManager(app)


class AuthError(Exception):
    pass


def with_auth_error_handling(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (AuthError, JWTExtendedException, PyJWTError) as e:
            app.logger.exception(f"Authentication error")
            raise GraphQLError(
                "Authentication error", extensions=dict(details=str(e))
            )

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
    db.session.commit()
    return {
        "access_token": create_access_token(
            {"id": user.id, "company_admin": user.is_company_admin},
            expires_delta=app.config["ACCESS_TOKEN_EXPIRATION"],
        ),
        "refresh_token": create_refresh_token(
            {"id": user.id, "nonce": new_refresh_nonce}, expires_delta=False
        ),
    }


class LoginMutation(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    access_token = graphene.String()
    refresh_token = graphene.String()

    @classmethod
    @with_auth_error_handling
    def mutate(cls, _, info, email, password):
        app.logger.info(f"{email} is attempting to log in")
        user = User.query.filter(User.email == email).one_or_none()
        if not user or not user.check_password(password):
            raise AuthError(
                f"Wrong email/password combination for email {email}"
            )
        return LoginMutation(**create_access_tokens_for(user))


class CheckMutation(graphene.Mutation):
    message = graphene.String()
    user_id = graphene.Int()

    @classmethod
    @with_auth_error_handling
    @jwt_required
    def mutate(cls, _, info):
        return CheckMutation(message="success", user_id=current_user.id)


class LogoutMutation(graphene.Mutation):
    message = graphene.String()

    @classmethod
    @with_auth_error_handling
    @jwt_required
    def mutate(cls, _, info):
        current_user.refresh_token_nonce = None
        db.session.commit()
        return LogoutMutation(message="success")


class RefreshMutation(graphene.Mutation):
    access_token = graphene.String()
    refresh_token = graphene.String()

    @classmethod
    @with_auth_error_handling
    @jwt_refresh_token_required
    def mutate(cls, _, info):
        return RefreshMutation(**create_access_tokens_for(current_user))


class AuthMutation(graphene.ObjectType):
    login = LoginMutation.Field()
    refresh = RefreshMutation.Field()
    check = CheckMutation.Field()
    logout = LogoutMutation.Field()
