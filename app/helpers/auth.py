from flask import Blueprint, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    jwt_refresh_token_required,
    current_user,
    JWTManager,
)
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt import PyJWTError
from datetime import timedelta
from functools import wraps

from app.controllers.utils import (
    request_data_schema,
    parse_request_with_schema,
)
from app.models.user import User
from app import app, db

jwt = JWTManager(app)

auth = Blueprint("auth", __name__)


class AuthError(Exception):
    pass


def with_auth_error_handling(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (AuthError, JWTExtendedException, PyJWTError) as e:
            return jsonify({"error": "Unauthorized access"}), 401

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


@auth.route("/refresh", methods=["POST"])
@with_auth_error_handling
@jwt_refresh_token_required
def refresh_user_token():
    return jsonify(create_access_tokens_for(current_user)), 200


@request_data_schema
class LoginData:
    email: str
    password: str


@auth.route("/login", methods=["POST"])
@with_auth_error_handling
@parse_request_with_schema(LoginData)
def login(data):
    user = User.query.filter(User.email == data.email).one_or_none()
    if not user or not user.check_password(data.password):
        raise AuthError()
    return jsonify(create_access_tokens_for(user)), 200


@auth.route("/logout", methods=["POST"])
@with_auth_error_handling
@jwt_required
def logout():
    current_user.refresh_token_nonce = None
    db.session.commit()
    return jsonify(), 200


@auth.route("/check", methods=["POST"])
@with_auth_error_handling
@jwt_required
def check():
    return jsonify({"message": "success", "user_id": current_user.id}), 200
