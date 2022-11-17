import graphene
import jwt
from enum import Enum
from flask import redirect, request, after_this_request, send_file, g, url_for
from uuid import uuid4
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode, unquote
from io import BytesIO

from webargs import fields
from flask_apispec import use_kwargs, doc
from marshmallow import Schema, validates_schema, ValidationError

from app.controllers.utils import atomic_transaction, Void
from app.data_access.user import UserOutput
from app.domain.permissions import (
    self_or_have_common_company,
    can_actor_read_mission,
)
from app.domain.user import (
    create_user,
    get_user_from_fc_info,
    bind_user_to_pending_employments,
)
from app.helpers.authentication import (
    current_user,
    create_access_tokens_for,
    UserTokens,
    UserTokensWithFC,
    AuthenticationError,
    unset_fc_auth_cookies,
    set_auth_cookies,
    require_auth,
    AuthenticatedMutation,
)
from app.helpers.authorization import (
    AuthorizationError,
)
from app.helpers.errors import (
    InvalidTokenError,
    TokenExpiredError,
    FCUserAlreadyRegisteredError,
    ActivationEmailDelayError,
)
from app.helpers.graphene_types import graphene_enum_type
from app.helpers.mail import MailjetError, MailingContactList
from app.helpers.france_connect import get_fc_user_info
from app.helpers.mail_type import EmailType
from app.helpers.pdf.mission_details import generate_mission_details_pdf
from app.helpers.pdf.work_days import generate_work_days_pdf_for
from app.helpers.tachograph import (
    generate_tachograph_parts,
    write_tachograph_archive,
    generate_tachograph_file_name,
)
from app.helpers.time import min_or_none, max_or_none
from app.models.queries import add_mission_relations
from app.templates.filters import full_format_day
from app.models import User, Mission
from app import app, db, mailer
from app.models.email import Email

TIMEZONE_DESC = "Fuseau horaire de l'utilisateur"


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
        subscribe_to_newsletter = graphene.Boolean(
            required=False,
            description="Consentement de l'utilisateur pour recevoir les mails newsletter",
        )
        is_employee = graphene.Boolean(
            required=False,
            description="Précise si le nouvel utilisateur est un travailleur mobile ou bien un gestionnaire. Vrai par défaut.",
        )
        timezone_name = graphene.String(
            required=False, description=TIMEZONE_DESC
        )

        way_heard_of_mobilic = graphene.String(
            required=False,
            description="Façon dont l'utilisateur a connu Mobilic.",
        )

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info, **data):
        with atomic_transaction(commit_at_end=True):
            has_subscribed_to_newsletter = data.pop(
                "subscribe_to_newsletter", False
            )
            is_employee = data.pop("is_employee", True)
            user = create_user(**data)
            user.create_activation_link()

        try:
            mailer.send_activation_email(user, is_employee=is_employee)
        except Exception as e:
            app.logger.exception(e)

        if has_subscribed_to_newsletter:
            try:
                newsletter_to_subscribe_to = MailingContactList.EMPLOYEES
                employment = user.employments[0] if user.employments else None
                if employment and employment.has_admin_rights:
                    newsletter_to_subscribe_to = MailingContactList.ADMINS

                user.subscribe_to_contact_list(newsletter_to_subscribe_to)
            except Exception as e:
                app.logger.exception(e)

        tokens = create_access_tokens_for(user)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(response, user_id=user.id, **tokens)
            return response

        return UserTokens(**tokens)


class ConfirmFranceConnectEmail(AuthenticatedMutation):
    class Arguments:
        email = graphene.String(
            required=True,
            description="Adresse email de contact, utilisée comme identifiant pour la connexion",
        )
        password = graphene.String(required=False, description="Mot de passe")
        timezone_name = graphene.String(
            required=False, description=TIMEZONE_DESC
        )
        way_heard_of_mobilic = graphene.String(
            required=False,
            description="Façon dont l'utilisateur a connu Mobilic.",
        )

    Output = UserOutput

    @classmethod
    def mutate(
        cls,
        _,
        info,
        email,
        password=None,
        timezone_name="Europe/Paris",
        way_heard_of_mobilic=None,
    ):
        with atomic_transaction(commit_at_end=True):
            if not current_user.france_connect_id or current_user.password:
                raise AuthorizationError("Actor has already a login")

            current_user.email = email
            current_user.has_confirmed_email = True
            current_user.timezone_name = timezone_name
            current_user.way_heard_of_mobilic = way_heard_of_mobilic
            current_user.create_activation_link()
            if password:
                current_user.password = password

        try:
            mailer.send_activation_email(current_user)
        except Exception as e:
            app.logger.exception(e)

        return current_user


class ChangeTimezone(AuthenticatedMutation):
    class Arguments:
        timezone_name = graphene.String(
            required=True,
            description=TIMEZONE_DESC,
        )

    Output = UserOutput

    @classmethod
    def mutate(cls, _, info, timezone_name):
        old_timezone_name = current_user.timezone_name
        if old_timezone_name != timezone_name:
            with atomic_transaction(commit_at_end=True):
                current_user.timezone_name = timezone_name
        return current_user


class ChangeEmail(AuthenticatedMutation):
    class Arguments:
        email = graphene.String(
            required=True,
            description="Adresse email de contact, utilisée comme identifiant pour la connexion",
        )

    Output = UserOutput

    @classmethod
    def mutate(cls, _, info, email):
        old_email = current_user.email
        if old_email != email:
            with atomic_transaction(commit_at_end=True):
                current_user.email = email
                current_user.has_confirmed_email = True
                current_user.create_activation_link()

                mailer.send_activation_email(
                    current_user, create_account=False, _disable_commit=True
                )

            try:
                for mailing_list in current_user.subscribed_mailing_lists:
                    mailer.remove_email_from_contact_list(
                        old_email, mailing_list
                    )
                    mailer.subscribe_email_to_contact_list(email, mailing_list)
                db.session.commit()
                bind_user_to_pending_employments(current_user)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
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


class ResendActivationEmail(AuthenticatedMutation):
    class Arguments:
        email = graphene.String(required=True)

    Output = Void

    @classmethod
    def mutate(cls, _, info, email):
        user = User.query.filter(User.email == email).one_or_none()
        if user:
            if user.id != current_user.id:
                raise AuthorizationError()
            last_activation_email_time = (
                db.session.query(db.func.max(Email.creation_time))
                .filter(
                    Email.user_id == user.id,
                    Email.type == EmailType.ACCOUNT_ACTIVATION,
                )
                .first()
            )[0]
            min_time_between_emails = app.config[
                "MIN_MINUTES_BETWEEN_ACTIVATION_EMAILS"
            ]
            if (
                not last_activation_email_time
                or datetime.now() - last_activation_email_time
                >= min_time_between_emails
            ):
                mailer.send_activation_email(user)
            else:
                raise ActivationEmailDelayError()
        else:
            raise AuthorizationError()
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
        return redirect(url_for(unquote(redirect_uri)), code=302)

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


@require_auth
def query_user(info, id=None):
    if id:
        user = User.query.get(id)
        if not user or not self_or_have_common_company(current_user, user):
            raise AuthorizationError("Forbidden access")
    else:
        user = current_user

    info.context.user_being_queried = user
    return user


class TachographBaseOptionsSchema(Schema):
    min_date = fields.Date(required=True)
    max_date = fields.Date(required=True)
    with_digital_signatures = fields.Boolean(required=False)

    @validates_schema
    def check_period_is_small_enough(self, data, **kwargs):
        if data["max_date"] - data["min_date"] > timedelta(days=64):
            raise ValidationError(
                "The requested period should be less than 64 days"
            )


@app.route("/users/generate_tachograph_file", methods=["POST"])
@doc(description="Génération de fichier C1B pour l'utilisateur et la période")
@use_kwargs(TachographBaseOptionsSchema(), apply=True)
@require_auth
def generate_tachograph_file(min_date, max_date, with_digital_signatures=True):
    tachograph_data = generate_tachograph_parts(
        current_user,
        start_date=max_or_none(
            min_date, getattr(g, "user_data_min_date", None)
        ),
        end_date=min_or_none(max_date, getattr(g, "user_data_max_date", None)),
        only_activities_validated_by_admin=False,
        with_signatures=with_digital_signatures,
        do_not_generate_if_empty=False,
    )
    file = BytesIO()
    file.write(write_tachograph_archive(tachograph_data))
    file.seek(0)

    return send_file(
        file,
        cache_timeout=0,
        mimetype="application/octet-stream",
        as_attachment=True,
        attachment_filename=generate_tachograph_file_name(current_user),
    )


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
    min_date,
    max_date,
):
    relevant_companies = [
        e.company
        for e in current_user.active_employments_between(min_date, max_date)
    ]
    pdf = generate_work_days_pdf_for(
        current_user,
        start_date=max_or_none(
            min_date, getattr(g, "user_data_min_date", None)
        ),
        end_date=min_or_none(max_date, getattr(g, "user_data_max_date", None)),
        include_support_activity=any(
            [c.require_support_activity for c in relevant_companies]
        ),
        include_expenditures=any(
            [c.require_expenditures for c in relevant_companies]
        ),
        include_transfers=any([c.allow_transfers for c in relevant_companies]),
    )

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        cache_timeout=0,
        attachment_filename=f"Relevé d'heures de {current_user.display_name} - {full_format_day(min_date)} au {full_format_day(max_date)}",
    )


class MissionExportSchema(Schema):
    mission_id = fields.Int(required=True)
    user_id = fields.Int(required=True)


@app.route("/users/generate_mission_export", methods=["POST"])
@doc(description="Export des détails de la mission au format PDF")
@use_kwargs(MissionExportSchema(), apply=True)
@require_auth
def generate_mission_export(mission_id, user_id):
    mission = add_mission_relations(Mission.query).get(mission_id)
    user = User.query.get(user_id)

    if (
        not mission
        or not user
        or not can_actor_read_mission(current_user, mission)
        or not can_actor_read_mission(user, mission)
    ):
        raise AuthorizationError()

    pdf = generate_mission_details_pdf(mission, user)

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        cache_timeout=0,
        attachment_filename=f"Détails de la mission {mission.name or mission.id} pour {user.display_name}",
    )


class WarningToDisableType(str, Enum):
    EMPLOYEE_VALIDATION = "employee-validation"
    ADMIN_MISSION_MODIFICATION = "admin-mission-modification"
    EMPLOYEE_GEOLOCATION_INFORMATION = "employee-geolocation-information"
    __description__ = """
Enumération des valeurs suivantes.
- "employee-validation" : alerte relative au caractère bloquant de la validation par le salarié
- "admin-mission-modification" : alerte relative à la visibilité des modifications de la mission par un gestionnaire 
- "employee-geolocation-information" : Modale d'information sur la géolocalisation 
"""


class DisableWarning(AuthenticatedMutation):
    class Arguments:
        warning_name = graphene.Argument(
            graphene_enum_type(WarningToDisableType),
            required=True,
            description="Alerte à désactiver",
        )

    Output = Void

    @classmethod
    def mutate(cls, _, info, warning_name):
        with atomic_transaction(commit_at_end=True):
            if warning_name not in current_user.disabled_warnings:
                current_user.disabled_warnings = [
                    *current_user.disabled_warnings,
                    warning_name,
                ]

        return Void(success=True)
