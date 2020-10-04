from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from authlib.oauth2.rfc6749 import grants
from authlib.integrations.flask_oauth2 import AuthorizationServer
from flask import Blueprint, request, make_response, jsonify
from flask_jwt_extended import jwt_required

from app import db, app
from app.helpers.authentication import (
    current_user,
    with_jwt_auth_error_handling,
)
from app.models import User
from app.helpers.oauth.models import (
    OAuth2AuthorizationCode,
    OAuth2Client,
    OAuth2Token,
)


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    def save_authorization_code(self, code, request):
        code_challenge = request.data.get("code_challenge")
        code_challenge_method = request.data.get("code_challenge_method")
        auth_code = OAuth2AuthorizationCode(
            code=code,
            client_id=request.client.id,
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            user_id=request.user.id,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
        db.session.add(auth_code)
        db.session.commit()
        return auth_code

    def query_authorization_code(self, code, client):
        auth_code = OAuth2AuthorizationCode.query.filter_by(
            code=code, client_id=client.id
        ).first()
        if auth_code and not auth_code.is_expired():
            return auth_code

    def delete_authorization_code(self, authorization_code):
        db.session.delete(authorization_code)
        db.session.commit()

    def authenticate_user(self, authorization_code):
        return User.query.get(authorization_code.user_id)


authorization = AuthorizationServer(
    app=app,
    query_client=lambda id: OAuth2Client.query.get(id),
    save_token=lambda *args, **kwargs: None,
)


def get_or_create_token(client, grant_type, user=None, **kwargs):
    valid_token = OAuth2Token.query.filter(
        OAuth2Token.client_id == client.id,
        OAuth2Token.user_id == user.id,
        OAuth2Token.revoked_at.is_(None),
    ).one_or_none()

    if not valid_token:
        try:
            valid_token = OAuth2Token(
                client_id=client.id, user_id=user.id, token=str(uuid4())
            )
            db.session.add(valid_token)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return get_or_create_token(client, grant_type, user=user, **kwargs)

    return {"token_type": "Bearer", "access_token": valid_token.token}


authorization.generate_token = get_or_create_token
authorization.register_grant(AuthorizationCodeGrant)

oauth_blueprint = Blueprint(__name__, "app.helpers.oauth")


@oauth_blueprint.route("/authorize", methods=["GET"])
@with_jwt_auth_error_handling
@jwt_required
def authorize():
    response = authorization.create_authorization_response(
        grant_user=current_user if not request.args.get("deny") else None
    )
    redirect_uri = response.headers.get("Location")
    status = 200
    if response.status_code < 300 or response.status_code >= 400:
        status = response.status_code
    return make_response(jsonify({"uri": redirect_uri}), status)


@oauth_blueprint.route("/parse_authorization_request", methods=["POST"])
def parse_authorization_request():
    try:
        grant = authorization.validate_consent_request()
        client = grant.request.client
        redirect_uri = grant.request.redirect_uri

    except Exception as e:
        app.logger.exception(e)
        return make_response(
            jsonify({"error": "Invalid or missing client id or redirect uri"}),
            400,
        )

    return jsonify({"client_name": client.name, "redirect_uri": redirect_uri})


@oauth_blueprint.route("/token", methods=["POST"])
def issue_token():
    return authorization.create_token_response()
