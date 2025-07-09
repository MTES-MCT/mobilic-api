import graphene
import jwt
from enum import Enum
from flask import redirect, request, after_this_request, send_file, g, url_for
from uuid import uuid4
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode, urlparse
from io import BytesIO

from webargs import fields
from flask_apispec import use_kwargs, doc
from marshmallow import Schema, validates_schema, ValidationError

from app.controllers.utils import atomic_transaction, Void
from app.data_access.user import UserOutput
from app.domain.gender import GENDER_DESCRIPTION, Gender
from app.domain.permissions import (
    self_or_have_common_company,
    can_actor_read_mission,
    only_self,
)
from app.domain.user import (
    create_user,
    get_user_from_fc_info,
    bind_user_to_pending_employments,
    change_user_password,
    is_user_related_to_onboarding_excluded_company,
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
    with_authorization_policy,
)
from app.helpers.errors import (
    InvalidTokenError,
    TokenExpiredError,
    FCUserAlreadyRegisteredError,
    ActivationEmailDelayError,
    InvalidParamsError,
)
from app.helpers.graphene_types import graphene_enum_type, Password
from app.helpers.mail import MailjetError, MailingContactList
from app.helpers.france_connect import get_fc_user_info, get_fc_config
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
from app.models.user_agreement import UserAgreementStatus
from app.templates.filters import full_format_day
from app.models import User, Mission, UserAgreement
from app import app, db, mailer
from app.models.email import Email
from app.helpers.graphene_types import Email as EmailGrapheneType

TIMEZONE_DESC = "Fuseau horaire de l'utilisateur"


class UserSignUp(graphene.Mutation):
    """
    Inscription d'un nouvel utilisateur.

    Retourne l'utilisateur nouvellement créé.
    """

    class Arguments:
        email = graphene.Argument(
            EmailGrapheneType,
            required=True,
            description="Adresse email, utilisée comme identifiant pour la connexion",
        )
        password = graphene.Argument(
            Password, required=True, description="Mot de passe"
        )
        first_name = graphene.String(required=True, description="Prénom")
        last_name = graphene.String(required=True, description="Nom")
        gender = graphene.Argument(
            graphene_enum_type(Gender),
            required=False,
            description=GENDER_DESCRIPTION,
        )
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
        phone_number = graphene.String(
            required=False, description="Numéro de téléphone"
        )
        accept_cgu = graphene.Boolean(
            required=False,
            description="Indique si l'utilisateur accepte les CGUs en vigueur",
        )

    Output = UserTokens

    @classmethod
    def mutate(cls, _, info, **data):
        accept_cgu = data.pop("accept_cgu", False)
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

        UserAgreement.get_or_create(
            user_id=user.id,
            initial_status=UserAgreementStatus.ACCEPTED
            if accept_cgu
            else UserAgreementStatus.PENDING,
        )

        tokens = create_access_tokens_for(user)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(response, user_id=user.id, **tokens)
            return response

        return UserTokens(**tokens)


class ConfirmFranceConnectEmail(AuthenticatedMutation):
    class Arguments:
        email = graphene.Argument(
            EmailGrapheneType,
            required=True,
            description="Adresse email de contact, utilisée comme identifiant pour la connexion",
        )
        password = graphene.Argument(
            Password, required=False, description="Mot de passe"
        )
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
        email = graphene.Argument(
            EmailGrapheneType,
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


class ChangeGender(AuthenticatedMutation):
    class Arguments:
        gender = graphene.Argument(
            graphene_enum_type(Gender),
            required=True,
            description=GENDER_DESCRIPTION,
        )

    Output = UserOutput

    @classmethod
    def mutate(cls, _, info, gender):
        with atomic_transaction(commit_at_end=True):
            current_user.gender = gender
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

            try:
                if not is_user_related_to_onboarding_excluded_company(user):
                    if (
                        len(user.current_company_ids_with_admin_rights or [])
                        > 0
                    ):
                        mailer.send_manager_onboarding_first_email(user)
                    else:
                        mailer.send_worker_onboarding_first_email(user)
            except Exception as e:
                app.logger.exception(e)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(
                response, **create_access_tokens_for(user), user_id=user.id
            )
            return response

        return user


class RequestPasswordReset(graphene.Mutation):
    class Arguments:
        mail = graphene.Argument(EmailGrapheneType, required=True)

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
        email = graphene.Argument(EmailGrapheneType, required=True)

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
        password = graphene.Argument(
            Password, required=True, description="Mot de passe"
        )

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

            change_user_password(user, password)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(
                response, **create_access_tokens_for(user), user_id=user.id
            )
            return response

        return user


class ResetPasswordConnected(AuthenticatedMutation):
    class Arguments:
        password = graphene.Argument(
            Password, required=True, description="Nouveau mot de passe"
        )
        user_id = graphene.Int(required=True)

    Output = Void

    @classmethod
    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda *args, **kwargs: kwargs["user_id"],
        error_message="Forbidden access",
    )
    def mutate(cls, _, info, password, user_id):
        user = User.query.get(user_id)
        if not user:
            raise (InvalidParamsError("Invalid user"))
        with atomic_transaction(commit_at_end=True):
            change_user_password(user, password, revoke_tokens=False)
        return Void(success=True)


@app.route("/fc/authorize")
def redirect_to_fc_authorize():
    base_url, client_id, _, api_version, _ = get_fc_config()

    from urllib.parse import parse_qs

    parsed_qs = parse_qs(request.query_string.decode("utf-8"))

    if api_version == "v2":
        fc_override = app.config.get("FC_V2_REDIRECT_URI_OVERRIDE")
        if fc_override:
            parsed_qs["redirect_uri"] = [fc_override]

    parsed_qs.update(
        {
            "state": [uuid4().hex],
            "nonce": [uuid4().hex],
            "response_type": ["code"],
            "scope": [
                "openid email given_name family_name preferred_username birthdate"
            ],
            "client_id": [client_id],
            "acr_values": ["eidas1"],
        }
    )

    final_qs = urlencode(parsed_qs, doseq=True, quote_via=quote)

    authorize_url = f"{base_url}/api/{api_version}/authorize?{final_qs}"

    if not _validate_fc_authorize_url(authorize_url, base_url):
        app.logger.error("Invalid FranceConnect authorize URL")
        return redirect("/", code=302)

    return redirect(authorize_url, code=302)


def _validate_redirect_url(url: str) -> bool:
    if not url:
        return False

    try:
        parsed = urlparse(url)

        if not parsed.scheme and not parsed.netloc:
            return url.startswith("/")

        trusted_domains = {
            "localhost",
            "127.0.0.1",
            "testdev.localhost",
            "mobilic.beta.gouv.fr",
            "mobilic.preprod.beta.gouv.fr",
        }

        if parsed.netloc.lower() in trusted_domains:
            return True

        if parsed.netloc == request.host:
            return True

        return False

    except Exception:
        return False


def _validate_fc_authorize_url(authorize_url: str, base_url: str) -> bool:
    try:
        parsed = urlparse(authorize_url)
        base_parsed = urlparse(base_url)

        if (
            parsed.scheme != base_parsed.scheme
            or parsed.netloc != base_parsed.netloc
        ):
            return False

        trusted_fc_domains = {
            "fcp-low.sbx.dev-franceconnect.fr",
            "fcp.integ01.dev-franceconnect.fr",
            "app.franceconnect.gouv.fr",
        }

        if parsed.netloc not in trusted_fc_domains:
            return False

        valid_paths = [
            "/api/v1/authorize",  # TODO: Remove after September 2025 when V1 is shut down # NOSONAR
            "/api/v2/authorize",
        ]

        return any(parsed.path.startswith(path) for path in valid_paths)

    except Exception:
        return False


def _validate_fc_logout_url(logout_url: str, base_url: str) -> bool:
    try:
        parsed = urlparse(logout_url)
        base_parsed = urlparse(base_url)

        if (
            parsed.scheme != base_parsed.scheme
            or parsed.netloc != base_parsed.netloc
        ):
            return False

        trusted_fc_domains = {
            "fcp-low.sbx.dev-franceconnect.fr",
            "fcp.integ01.dev-franceconnect.fr",
            "app.franceconnect.gouv.fr",
        }

        if parsed.netloc not in trusted_fc_domains:
            return False

        valid_paths = [
            "/api/v1/logout",  # TODO: Remove after September 2025 when V1 is shut down # NOSONAR
            "/api/v2/session/end",
        ]

        return any(parsed.path.startswith(path) for path in valid_paths)

    except Exception:
        return False


@app.route("/fc/logout")
def redirect_to_fc_logout():
    fc_token_hint = request.cookies.get("fct")

    @after_this_request
    def unset_fc_cookies(response):
        unset_fc_auth_cookies(response)
        return response

    if not fc_token_hint:
        app.logger.warning("FranceConnect logout attempt without token")
        return redirect("/logout", code=302)

    base_url, _, _, api_version, _ = get_fc_config()

    query_params = {"state": uuid4().hex, "id_token_hint": fc_token_hint}

    # v2 requires post_logout_redirect_uri
    if api_version == "v2":
        default_logout_uri = f"{request.host_url}logout"

        fc_logout_override = app.config.get("FC_V2_REDIRECT_URI_OVERRIDE")
        if fc_logout_override:

            default_logout_uri = fc_logout_override.replace(
                "/fc-callback", "/logout"
            )

        query_params["post_logout_redirect_uri"] = default_logout_uri
    # TODO: Remove V1 support after September 2025 when V1 is shut down # NOSONAR

    logout_endpoint = (
        "session/end" if api_version == "v2" else "logout"
    )  # TODO: Remove V1 support after September 2025 # NOSONAR

    final_logout_url = f"{base_url}/api/{api_version}/{logout_endpoint}?{urlencode(query_params, quote_via=quote)}"

    if not _validate_fc_logout_url(final_logout_url, base_url):
        app.logger.error("Invalid FranceConnect logout URL")
        return redirect("/logout", code=302)

    app.logger.info(f"FranceConnect {api_version} logout initiated")

    return redirect(final_logout_url, code=302)


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
    employee_version = fields.Boolean(required=False)

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
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=generate_tachograph_file_name(current_user),
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
        include_other_task=any(
            [c.allow_other_task for c in relevant_companies]
        ),
    )

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Relevé d'heures de {current_user.display_name} - {full_format_day(min_date)} au {full_format_day(max_date)}",
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
        download_name=f"Détails de la mission {mission.name or mission.id} pour {user.display_name}",
    )


class WarningToDisableType(str, Enum):
    EMPLOYEE_VALIDATION = "employee-validation"
    ADMIN_MISSION_MODIFICATION = "admin-mission-modification"
    EMPLOYEE_GEOLOCATION_INFORMATION = "employee-geolocation-information"
    EMPLOYEE_OFF_CREATION = "employee-off-creation"
    __description__ = """
Enumération des valeurs suivantes.
- "employee-validation" : alerte relative au caractère bloquant de la validation par le salarié
- "admin-mission-modification" : alerte relative à la visibilité des modifications de la mission par un gestionnaire 
- "employee-geolocation-information" : Modale d'information sur la géolocalisation 
- "employee-off-creation" : alerte relative au caractère bloquant de la création d'une absence par le salarié
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


class ChangeName(AuthenticatedMutation):
    class Arguments:
        user_id = graphene.Int(
            required=True,
            description="Identifiant de l'utilisateur dont le nom doit être changé",
        )

        new_last_name = graphene.String(
            required=True,
            description="Nouveau nom",
        )

        new_first_name = graphene.String(
            required=True,
            description="Nouveau prénom",
        )

    Output = UserOutput

    @classmethod
    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda *args, **kwargs: kwargs["user_id"],
        error_message="Forbidden access",
    )
    def mutate(cls, _, info, user_id, new_first_name, new_last_name):
        user = User.query.get(user_id)
        with atomic_transaction(commit_at_end=True):
            user.last_name = new_last_name
            user.first_name = new_first_name
        return user


class ChangePhoneNumber(AuthenticatedMutation):
    class Arguments:
        user_id = graphene.Int(
            required=True,
            description="Identifiant de l'utilisateur dont le numéro de téléphone doit être changé",
        )

        new_phone_number = graphene.String(
            required=True,
            description="Nouveau numéro de téléphone",
        )

    Output = UserOutput

    @classmethod
    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda *args, **kwargs: kwargs["user_id"],
        error_message="Forbidden access",
    )
    def mutate(cls, _, info, user_id, new_phone_number):
        user = User.query.get(user_id)
        with atomic_transaction(commit_at_end=True):
            user.phone_number = new_phone_number
        return user
