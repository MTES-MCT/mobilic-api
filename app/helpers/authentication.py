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
from datetime import timedelta
from functools import wraps

from app.controllers.utils import request_data_schema
from app.data_access.utils import with_input_from_schema
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
            raise GraphQLError(
                "Authentication error", extensions=dict(details=str(e))
            )

    return wrapper


@jwt.user_loader_callback_loader
def get_user_from_token_identity(identity):
    # Refresh token
    if type(identity) is dict:
        user = User.query.get(identity["id"])
        nonce = identity["nonce"]
        if (
            user
            and user.refresh_token_nonce
            and nonce == user.refresh_token_nonce
        ):
            return user
        return None

    # Access token
    user = User.query.get(identity)
    if user and user.refresh_token_nonce:
        return user
    return None


def create_access_tokens_for(user):
    new_refresh_nonce = user.generate_refresh_token_nonce()
    db.session.commit()
    return {
        "access_token": create_access_token(
            user.id,
            expires_delta=timedelta(
                minutes=app.config["ACCESS_TOKEN_EXPIRATION"]
            ),
        ),
        "refresh_token": create_refresh_token(
            {"id": user.id, "nonce": new_refresh_nonce}, expires_delta=False
        ),
    }


@request_data_schema
class LoginData:
    email: str
    password: str


@with_input_from_schema(LoginData)
class LoginMutation(graphene.Mutation):
    access_token = graphene.String()
    refresh_token = graphene.String()

    @classmethod
    @with_auth_error_handling
    def mutate(cls, _, info, input: LoginData):
        user = User.query.filter(User.email == input.email).one_or_none()
        if not user or not user.check_password(input.password):
            raise AuthError("Wrong credentials")
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
