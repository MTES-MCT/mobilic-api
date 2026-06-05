from datetime import datetime, timedelta, timezone

import graphene
from flask import after_this_request, jsonify, request
from flask_jwt_extended import (
    decode_token,
    jwt_required,
    get_jwt_identity,
    current_user as current_actor,
)
from app import app, db
from app.controllers.utils import Void
from app.domain.totp import verify_totp_code
from app.domain.user import (
    increment_user_password_tries,
    reset_user_password_tries,
)
from app.helpers.authentication import (
    create_access_tokens_for,
    create_totp_challenge_token,
    set_auth_cookies,
    LoginOutput,
    UserTokens,
    logout,
    refresh_token,
    wrap_jwt_errors,
    unset_auth_cookies,
)
from app.helpers.authentication_controller import refresh_controller_token
from app.helpers.errors import (
    AuthenticationError,
    BlockedAccountError,
    BadPasswordError,
)
from app.helpers.graphene_types import Email
from app.models import User, UserAgreement
from app.models.user import UserAccountStatus


class LoginMutation(graphene.Mutation):
    """
    Authenticate via email/password.

    Returns an access token and a refresh token.
    If the user has 2FA TOTP enabled, returns a temporary token with totp_required=true.
    """

    class Arguments:
        email = graphene.Argument(
            Email,
            required=True,
        )
        password = graphene.String(required=True)

    Output = LoginOutput

    @classmethod
    def mutate(cls, _, info, email, password):
        if email in app.config["USERS_BLACKLIST"]:
            raise AuthenticationError(
                f"Wrong email/password combination for email {email}"
            )

        user = User.query.filter(User.email == email).one_or_none()

        is_blacklisted = UserAgreement.is_user_blacklisted(user_id=user.id)

        if is_blacklisted:
            raise AuthenticationError(
                f"Wrong email/password combination for email {email}"
            )

        if not user or (
            not app.config["DISABLE_PASSWORD_CHECK"] and not user.password
        ):
            raise AuthenticationError(
                f"Wrong email/password combination for email {email}"
            )
        elif not app.config["DISABLE_PASSWORD_CHECK"]:
            if user.status == UserAccountStatus.BLOCKED_BAD_PASSWORD:
                raise BlockedAccountError
            elif not user.check_password(password):
                increment_user_password_tries(user)
                db.session.commit()
                if user.status == UserAccountStatus.BLOCKED_BAD_PASSWORD:
                    raise BlockedAccountError
                raise BadPasswordError(
                    f"Wrong email/password combination for email {email}",
                    nb_bad_tries=user.nb_bad_password_tries,
                    max_possible_tries=app.config[
                        "NB_BAD_PASSWORD_TRIES_BEFORE_BLOCKING"
                    ],
                )
            reset_user_password_tries(user)

        totp_cred = user.totp_credential
        if totp_cred and totp_cred.enabled:
            temp_token = create_totp_challenge_token(user)
            return LoginOutput(
                access_token=temp_token,
                refresh_token=None,
                totp_required=True,
            )

        tokens = create_access_tokens_for(user)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(response, user_id=user.id, **tokens)
            return response

        return LoginOutput(**tokens, totp_required=False)


TOTP_MAX_ATTEMPTS = 5
TOTP_RATE_LIMIT_WINDOW = timedelta(minutes=5)


class ValidateTOTPLogin(graphene.Mutation):
    """
    Validate TOTP code after a 2FA login.
    Requires the temporary challenge token in the Authorization header.
    """

    class Arguments:
        code = graphene.String(required=True)

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info, code):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthenticationError("Missing authorization header")

        token_str = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token_str)
        except Exception:
            raise AuthenticationError(
                "Invalid or expired TOTP challenge token"
            )

        identity = payload.get("identity")
        if not identity or not identity.get("totp_required"):
            raise AuthenticationError("Invalid TOTP challenge token")

        user = User.query.get(identity["id"])
        if not user:
            raise AuthenticationError("Invalid TOTP challenge token")

        totp_cred = user.totp_credential
        if not totp_cred:
            raise AuthenticationError("TOTP not configured")

        now = datetime.now(tz=timezone.utc)
        if totp_cred.failed_attempts >= TOTP_MAX_ATTEMPTS:
            if (
                totp_cred.last_failed_at
                and now - totp_cred.last_failed_at < TOTP_RATE_LIMIT_WINDOW
            ):
                raise BlockedAccountError
            totp_cred.failed_attempts = 0

        if not verify_totp_code(totp_cred.secret, code):
            totp_cred.failed_attempts += 1
            totp_cred.last_failed_at = now
            db.session.commit()
            raise AuthenticationError("Invalid TOTP code")

        totp_cred.failed_attempts = 0
        totp_cred.last_failed_at = None
        db.session.commit()

        tokens = create_access_tokens_for(user)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(response, user_id=user.id, **tokens)
            return response

        return UserTokens(**tokens)


class LogoutMutation(graphene.Mutation):
    """Invalidate the existing refresh token for the user."""

    Output = Void

    @classmethod
    def mutate(cls, _, info):
        logout()
        return Void(success=True)


class RefreshMutation(graphene.Mutation):
    """
    Refresh the access token. The request must include the
    "Authorization: Bearer <REFRESH_TOKEN>" header.

    A refresh token can only be used once.
    Returns a new access token and a new refresh token.
    """

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info):
        return UserTokens(**refresh_token())


@app.route("/token/refresh", methods=["POST"])
@wrap_jwt_errors
@jwt_required(refresh=True)
def rest_refresh_token():
    try:
        if not current_actor:
            raise AuthenticationError("Current user not found")

        identity = get_jwt_identity()
        if identity and identity.get("controller"):
            tokens = refresh_controller_token()
        else:
            tokens = refresh_token()
        return jsonify(tokens), 200
    except AuthenticationError as e:

        @after_this_request
        def unset_cookies(response):
            unset_auth_cookies(response)
            return response

        raise


@app.route("/token/logout", methods=["POST"])
def rest_logout():
    @after_this_request
    def unset_cookies(response):
        unset_auth_cookies(response)
        return response

    logout()
    return jsonify({"success": True}), 200
