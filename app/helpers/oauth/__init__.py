from authlib.oauth2.rfc6749 import grants
from authlib.integrations.flask_oauth2 import AuthorizationServer
from flask import Blueprint, request, make_response, jsonify
from flask_jwt_extended import jwt_required

from app import db, app
from app.helpers.authentication import create_access_tokens_for, current_user
from app.models import User
from app.helpers.oauth.models import OAuth2AuthorizationCode, OAuth2Client


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
    save_token=lambda: None,
)


def generate_token(
    client,
    grant_type,
    user=None,
    scope=None,
    expires_in=None,
    include_refresh_token=True,
):
    return create_access_tokens_for(
        user,
        client_id=client.id,
        include_refresh_token=include_refresh_token,
        include_additional_info=True,
    )


authorization.generate_token = generate_token
authorization.register_grant(AuthorizationCodeGrant)

oauth_blueprint = Blueprint(__name__, "app.helpers.oauth")


@oauth_blueprint.route("/authorize", methods=["GET"])
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


@oauth_blueprint.route("/parse_authorization_request")
def parse_authorization_request():
    try:
        client_id = int(request.args["client_id"])
        redirect_uri = request.args["redirect_uri"]
        client = OAuth2Client.query.filter(OAuth2Client.id == client_id).one()

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
