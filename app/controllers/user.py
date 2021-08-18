import graphene
import jwt
from flask import redirect, request, after_this_request, send_file
from uuid import uuid4
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode, unquote

from webargs import fields
from flask_apispec import use_kwargs, doc
from marshmallow import Schema, validates_schema, ValidationError

from app.controllers.utils import atomic_transaction, Void
from app.data_access.user import UserOutput
from app.domain.permissions import self_or_company_admin
from app.domain.user import create_user, get_user_from_fc_info
from app.helpers.authentication import (
    current_user,
    create_access_tokens_for,
    UserTokens,
    UserTokensWithFC,
    AuthenticationError,
    unset_fc_auth_cookies,
    set_auth_cookies,
    require_auth,
)
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated,
    AuthorizationError,
)
from app.helpers.errors import (
    InvalidTokenError,
    TokenExpiredError,
    FCUserAlreadyRegisteredError,
)
from app.helpers.mail import MailjetError
from app.helpers.france_connect import get_fc_user_info
from app.helpers.pdf import generate_work_days_pdf_for
from app.templates.filters import full_format_day
from app.models import User
from app import app, db, mailer


class UserSignUp(graphene.Mutation):
    """
    Inscription d'un nouvel utilisateur.

    Retourne l'utilisateur nouvellement créé.
    """

    class Arguments:
        email = graphene.String(
            required=True,
            description="Adresse email, utilisée comme identifiant pour la connexion",
        )
        password = graphene.String(required=True, description="Mot de passe")
        first_name = graphene.String(required=True, description="Prénom")
        last_name = graphene.String(required=True, description="Nom")
        invite_token = graphene.String(
            required=False, description="Lien d'invitation"
        )
        ssn = graphene.String(
            required=False, description="Numéro de sécurité sociale"
        )

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info, **data):
        with atomic_transaction(commit_at_end=True):
            user = create_user(**data)
            user.create_activation_link()

        try:
            mailer.send_activation_email(user)
        except Exception as e:
            app.logger.exception(e)

        tokens = create_access_tokens_for(user)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(response, user_id=user.id, **tokens)
            return response

        return UserTokens(**tokens)


class ConfirmFranceConnectEmail(graphene.Mutation):
    class Arguments:
        email = graphene.String(
            required=True,
            description="Adresse email de contact, utilisée comme identifiant pour la connexion",
        )
        password = graphene.String(required=False, description="Mot de passe")

    Output = UserOutput

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, email, password=None):
        with atomic_transaction(commit_at_end=True):
            if not current_user.france_connect_id or current_user.password:
                raise AuthorizationError("Actor has already a login")

            current_user.email = email
            current_user.has_confirmed_email = True
            current_user.create_activation_link()
            if password:
                current_user.password = password

        try:
            mailer.send_activation_email(current_user)
        except Exception as e:
            app.logger.exception(e)

        return current_user


class ChangeEmail(graphene.Mutation):
    class Arguments:
        email = graphene.String(
            required=True,
            description="Adresse email de contact, utilisée comme identifiant pour la connexion",
        )

    Output = UserOutput

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, email):
        with atomic_transaction(commit_at_end=True):
            if current_user.email != email:
                current_user.email = email
                current_user.has_confirmed_email = True
                current_user.create_activation_link()

        try:
            mailer.send_activation_email(current_user, create_account=False)
        except Exception as e:
            app.logger.exception(e)

        return current_user


class ActivateEmail(graphene.Mutation):
    class Arguments:
        token = graphene.String(required=True)

    Output = UserOutput

    @classmethod
    def mutate(cls, _, info, token):
        with atomic_transaction(commit_at_end=True):
            try:
                decoded_token = jwt.decode(
                    token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
                )

                user_id = decoded_token["user_id"]
                activation_token = decoded_token["token"]
                email = decoded_token["email"]
                expires_at = decoded_token["expires_at"]
            except Exception as e:
                raise InvalidTokenError(
                    f"Token is invalid : {e}", should_alert_team=True
                )

            if expires_at < datetime.now().timestamp():
                raise TokenExpiredError("Token has expired")

            try:
                user = User.query.get(user_id)
                current_activation_token = user.activation_email_token
            except Exception as e:
                raise InvalidTokenError(
                    "Invalid user in token", should_alert_team=True
                )

            if (
                email != user.email
                or not current_activation_token
                or activation_token != current_activation_token
            ):
                raise InvalidTokenError(
                    "Token is no more valid because it has been redeemed or a new token exists"
                )

            user.has_activated_email = True

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(
                response, **create_access_tokens_for(user), user_id=user.id
            )
            return response

        return user


class RequestPasswordReset(graphene.Mutation):
    class Arguments:
        mail = graphene.String(required=True)

    Output = Void

    @classmethod
    def mutate(cls, _, info, mail):
        user = User.query.filter(User.email == mail).one_or_none()
        if user:
            try:
                mailer.send_reset_password_email(user)
            except MailjetError as e:
                app.logger.exception(e)
                return RequestPasswordReset(message="failure")
        return Void(success=True)


class ResetPassword(graphene.Mutation):
    class Arguments:
        token = graphene.String(required=True)
        password = graphene.String(required=True)

    Output = UserOutput

    @classmethod
    def mutate(cls, _, info, token, password):
        with atomic_transaction(commit_at_end=True):
            try:
                decoded_token = jwt.decode(
                    token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
                )

                user_id = decoded_token["user_id"]
                current_password = decoded_token["hash"]
                expires_at = decoded_token["expires_at"]
            except Exception as e:
                raise InvalidTokenError(f"Token is invalid : {e}")

            if expires_at < datetime.now().timestamp():
                raise TokenExpiredError("Token has expired")

            user = User.query.get(user_id)
            if not user:
                raise InvalidTokenError("Invalid user in token")

            if current_password != user.password:
                raise InvalidTokenError(
                    "Token is no more valid because it has been redeemed or a new token exists"
                )

            user.revoke_all_tokens()
            user.password = password

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(
                response, **create_access_tokens_for(user), user_id=user.id
            )
            return response

        return user


@app.route("/fc/authorize")
def redirect_to_fc_authorize():
    query_params = {
        "state": uuid4().hex,
        "nonce": uuid4().hex,
        "response_type": "code",
        "scope": "openid email given_name family_name preferred_username birthdate",
        "client_id": app.config["FC_CLIENT_ID"],
        "acr_values": "eidas1",
    }
    return redirect(
        f"{app.config['FC_URL']}/api/v1/authorize?{request.query_string.decode('utf-8')}&{urlencode(query_params, quote_via=quote)}",
        code=302,
    )


@app.route("/fc/logout")
def redirect_to_fc_logout():
    fc_token_hint = request.cookies.get("fct")

    @after_this_request
    def unset_fc_cookies(response):
        unset_fc_auth_cookies(response)
        return response

    if not fc_token_hint:
        app.logger.warning(
            "Attempt do disconnect from FranceConnect a user who is not logged in"
        )

        redirect_uri = request.args.get("post_logout_redirect_uri")
        return redirect(unquote(redirect_uri), code=302)

    query_params = {"state": uuid4().hex, "id_token_hint": fc_token_hint}

    return redirect(
        f"{app.config['FC_URL']}/api/v1/logout?{request.query_string.decode('utf-8')}&{urlencode(query_params, quote_via=quote)}",
        code=302,
    )


class FranceConnectLogin(graphene.Mutation):
    class Arguments:
        authorization_code = graphene.String(required=True)
        invite_token = graphene.String(
            required=False, description="Lien d'invitation"
        )
        state = graphene.String(required=True)
        original_redirect_uri = graphene.String(required=True)
        create = graphene.Boolean(required=False)

    Output = UserTokensWithFC

    @classmethod
    def mutate(
        cls,
        _,
        info,
        authorization_code,
        original_redirect_uri,
        state,
        invite_token=None,
        create=False,
    ):
        with atomic_transaction(commit_at_end=True):
            fc_user_info, fc_token = get_fc_user_info(
                authorization_code, original_redirect_uri
            )
            user = get_user_from_fc_info(fc_user_info)

            if not create and not user:
                raise AuthenticationError("User does not exist")

            if create and user and user.email:
                # TODO : raise proper error
                raise FCUserAlreadyRegisteredError(
                    "User is already registered"
                )

            if not user:
                user = create_user(
                    first_name=fc_user_info.get("given_name"),
                    last_name=fc_user_info.get("family_name"),
                    email=fc_user_info.get("email"),
                    invite_token=invite_token,
                    fc_info=fc_user_info,
                )

        tokens = create_access_tokens_for(user)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(
                response, user_id=user.id, **tokens, fc_token=fc_token
            )
            return response

        return UserTokensWithFC(**tokens, fc_token=fc_token)


class Query(graphene.ObjectType):
    user = graphene.Field(
        UserOutput,
        id=graphene.Int(required=True),
        description="Consultation des informations d'un utilisateur, notamment ses enregistrements",
    )

    me = graphene.Field(
        UserOutput,
        description="Consultation des informations de l'utilisateur authentifié",
    )

    def resolve_user(self, info, id):
        return query_user(info, id=id)

    def resolve_me(self, info):
        return query_user(info)


@with_authorization_policy(authenticated)
def query_user(info, id=None):
    if id:
        user = User.query.get(id)
        if not user or not self_or_company_admin(current_user, user):
            raise AuthorizationError("Forbidden access")
    else:
        user = current_user

    info.context.user_being_queried = user
    app.logger.info(f"Sending user data for {user}")
    return user


class PDFExportSchema(Schema):
    min_date = fields.Date(required=True)
    max_date = fields.Date(required=True)

    @validates_schema
    def check_period_is_small_enough(self, data, **kwargs):
        if data["max_date"] - data["min_date"] > timedelta(days=366):
            raise ValidationError(
                "The requested period should be less than 1 year"
            )


@app.route("/users/generate_pdf_export", methods=["POST"])
@doc(description="Génération d'un relevé d'heures au format PDF")
@use_kwargs(PDFExportSchema(), apply=True)
@require_auth
def generate_pdf_export(
    min_date, max_date,
):
    relevant_companies = [
        e.company
        for e in current_user.active_employments_between(min_date, max_date)
    ]
    pdf = generate_work_days_pdf_for(
        current_user,
        min_date,
        max_date,
        include_support_activity=any(
            [c.require_support_activity for c in relevant_companies]
        ),
        include_expenditures=any(
            [c.require_expenditures for c in relevant_companies]
        ),
    )

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        cache_timeout=0,
        attachment_filename=f"Relevé d'heures de {current_user.display_name} - {full_format_day(min_date)} au {full_format_day(max_date)}",
    )
