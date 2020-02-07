from flask import Blueprint, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    jwt_refresh_token_required,
    current_user,
)
from datetime import timedelta

from app.controllers.utils import (
    request_data_schema,
    parse_request_with_schema,
)
from app.models.user import User
from app import app, db

auth = Blueprint(__name__)


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
        raise Exception

    # Access token
    user = User.query.get(identity)
    if user and user.refresh_token_nonce:
        return user
    raise Exception


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
@jwt_refresh_token_required
def refresh_user_token():
    return jsonify(create_access_tokens_for(current_user)), 200


@request_data_schema
class LoginData:
    email: str
    password: str


@auth.route("/login", methods=["POST"])
@parse_request_with_schema(LoginData)
def login(data):
    user = User.query.filter(User.email == data.email).one()
    if not user.check_password(data.password):
        raise Exception
    return jsonify(create_access_tokens_for(user)), 200


@auth.route("/logout", methods=["POST"])
@jwt_required
def logout():
    current_user.refresh_token_nonce = None
    db.session.commit()
    return jsonify(), 200
