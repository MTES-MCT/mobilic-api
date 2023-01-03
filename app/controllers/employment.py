from datetime import datetime, date, timedelta
from uuid import uuid4

import graphene
from flask import after_this_request
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app import app, db, mailer
from app.controllers.user import TIMEZONE_DESC
from app.controllers.utils import atomic_transaction, Void
from app.domain.employment import create_employment_by_third_party_if_needed
from app.domain.permissions import company_admin
from app.domain.third_party_employment import (
    create_third_party_employment_link_if_needed,
)
from app.domain.user import create_user_by_third_party_if_needed
from app.helpers.api_key_authentication import (
    ProtectedMutation,
    check_protected_client_id_company_id,
    request_client_id,
)
from app.helpers.authentication import (
    current_user,
    set_auth_cookies,
    create_access_tokens_for,
    AuthenticatedMutation,
    require_auth_with_write_access,
)
from app.helpers.authorization import (
    with_authorization_policy,
    active,
    AuthorizationError,
    with_protected_authorization_policy,
)
from app.helpers.errors import (
    InvalidParamsError,
    InvalidTokenError,
    InvalidResourceError,
    UserSelfChangeRoleError,
    UserSelfTerminateEmploymentError,
    ActivityExistAfterEmploymentEndDate,
    EmploymentAlreadyTerminated,
)
from app.helpers.graphene_types import Email
from app.helpers.mail import MailjetError
from app.helpers.oauth.models import ThirdPartyClientEmployment
from app.models import Company, User
from app.models.employment import (
    EmploymentOutput,
    Employment,
    EmploymentRequestValidationStatus,
)
from app.models.queries import query_activities

MAX_SIZE_OF_INVITATION_BATCH = 100
MAILJET_BATCH_SEND_LIMIT = 50


class ThirdPartyEmployee(graphene.InputObjectType):
    email = graphene.Field(Email, required=True, description="Adresse email")
    first_name = graphene.String(required=True, description="Prénom")
    last_name = graphene.String(required=True, description="Nom")
    external_id = graphene.String(
        required=False,
        description="Identifiant du salarié dans le logiciel tiers",
    )
    has_admin_rights = graphene.Argument(
        graphene.Boolean,
        required=False,
        description="Précise si le salarié à rattacher est gestionnaire de l'entreprise, et s'il pourra donc avoir les droits de consultation et d'administration associés. Par défaut, si l'argument n'est pas présent le salarié n'aura pas les droits.",
        default_value=False,
    )
    timezone_name = graphene.Argument(
        graphene.String,
        required=False,
        description=TIMEZONE_DESC,
        default_value="Europe/Paris",
    )


class SyncThirdPartyEmployees(ProtectedMutation):
    """
    Permet qu'un logiciel tiers puisse synchroniser sa base salarié avec les employment dans Mobilic.
    Les salariés vont recevoir plusieurs mails :
     - pour potentiellement la création de compte le cas échéant
     - pour la demande d'accès de leurs données par le logiciel tiers.
    """

    class Arguments:
        company_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de l'entreprise de rattachement",
        )
        employees = graphene.List(
            ThirdPartyEmployee,
            required=True,
            description="Liste des employés à rattacher à l'entreprise",
        )

    Output = graphene.List(EmploymentOutput)

    @classmethod
    @with_protected_authorization_policy(
        authorization_rule=check_protected_client_id_company_id,
        get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
        error_message="You do not have access to the provided company id",
    )
    def mutate(cls, _, info, company_id, employees):
        with atomic_transaction(commit_at_end=True):
            for employee in employees:
                user = create_user_by_third_party_if_needed(
                    employee.email,
                    employee.first_name,
                    employee.last_name,
                    employee.timezone_name,
                )

                employment = create_employment_by_third_party_if_needed(
                    user.id,
                    company_id,
                    employee.email,
                    employee.has_admin_rights,
                    employee.external_id,
                )

                create_third_party_employment_link_if_needed(
                    employment.id, client_id=request_client_id()
                )

        list_to_return = (
            Employment.query.filter(
                Employment.company_id == company_id, ~Employment.is_dismissed
            )
            .join(
                ThirdPartyClientEmployment,
                ThirdPartyClientEmployment.employment_id == Employment.id,
            )
            .all()
        )
        return list_to_return


class CreateEmployment(AuthenticatedMutation):
    """
    Invitation de rattachement d'un travailleur mobile à une entreprise. L'invitation doit être approuvée par le salarié pour être effective.

    Retourne le rattachement.
    """

    class Arguments:
        company_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de l'entreprise de rattachement",
        )
        user_id = graphene.Argument(
            graphene.Int,
            required=False,
            description="Identifiant du travailleur à rattacher. Optionnel, soit un identifiant soit un email doit être transmis.",
        )
        mail = graphene.Argument(
            graphene.String,
            required=False,
            description="Email du travailleur pour invitation. Optionnel, soit un identifiant soit un email doit être transmis.",
        )
        start_date = graphene.Argument(
            graphene.Date,
            required=False,
            description="Date de début du rattachement. Si non précisée, la date du jour sera utilisée.",
        )
        end_date = graphene.Argument(
            graphene.Date,
            required=False,
            description="Date de fin du rattachement. Optionnelle.",
        )
        has_admin_rights = graphene.Argument(
            graphene.Boolean,
            required=False,
            description="Précise si le salarié rattaché est gestionnaire de l'entreprise, et s'il pourra donc avoir les droits de consultation et d'administration associés. Par défaut, si l'argument n'est pas présent le salarié n'aura pas les droits.",
        )

    Output = EmploymentOutput

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
    )
    def mutate(cls, _, info, **employment_input):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            company = Company.query.get(employment_input["company_id"])
            user_id = employment_input.get("user_id")
            user_email = employment_input.get("mail")

            if (user_id is None) == (user_email is None):
                raise InvalidParamsError(
                    "Exactly one of userId or mail should be provided."
                )

            user = None
            invite_token = uuid4().hex
            if user_id:
                user = User.query.options(selectinload(User.employments)).get(
                    employment_input["user_id"]
                )
                if not user:
                    raise InvalidResourceError(
                        "Invalid user id", should_alert_team=False
                    )
            if user_email:
                user = (
                    User.query.options(selectinload(User.employments))
                    .filter(func.lower(User.email) == func.lower(user_email))
                    .one_or_none()
                )
            if user:
                user_id = user.id

            start_date = employment_input.get("start_date", date.today())

            employment = Employment(
                reception_time=reception_time,
                submitter=current_user,
                validation_status=EmploymentRequestValidationStatus.PENDING,
                start_date=start_date,
                end_date=employment_input.get("end_date"),
                company=company,
                has_admin_rights=employment_input.get("has_admin_rights"),
                user=user,
                user_id=user_id,
                invite_token=invite_token,
                email=employment_input.get("mail"),
            )
            db.session.add(employment)

            try:
                mailer.send_employee_invite(employment)
            except MailjetError as e:
                if not user:
                    raise e
                app.logger.exception(e)

        return employment


class CreateWorkerEmploymentsFromEmails(AuthenticatedMutation):
    """
    Invitation de rattachement d'un travailleur mobile à une entreprise. L'invitation doit être approuvée par le salarié pour être effective.

    Retourne le rattachement.
    """

    class Arguments:
        company_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de l'entreprise de rattachement",
        )
        mails = graphene.Argument(
            graphene.List(graphene.String),
            required=True,
            description="Liste d'emais à rattacher.",
        )

    Output = graphene.List(EmploymentOutput)

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
    )
    def mutate(cls, _, info, company_id, mails):
        with atomic_transaction(commit_at_end=True):
            print(mails)
            if len(mails) > MAX_SIZE_OF_INVITATION_BATCH:
                raise InvalidParamsError(
                    f"List of emails to invite cannot exceed {MAX_SIZE_OF_INVITATION_BATCH} in length"
                )
            reception_time = datetime.now()
            company = Company.query.get(company_id)

            employments = [
                Employment(
                    reception_time=reception_time,
                    submitter=current_user,
                    validation_status=EmploymentRequestValidationStatus.PENDING,
                    start_date=reception_time.date(),
                    end_date=None,
                    company=company,
                    has_admin_rights=False,
                    invite_token=uuid4().hex,
                    email=mail,
                )
                for mail in mails
            ]
            db.session.flush()

            messages = []
            for cursor in range(0, len(mails), MAILJET_BATCH_SEND_LIMIT):
                messages.extend(
                    mailer.batch_send_employee_invites(
                        employments[
                            cursor : (cursor + MAILJET_BATCH_SEND_LIMIT)
                        ]
                    )
                )
            unsent_employments = []
            for index, message in enumerate(messages):
                if isinstance(message.response, MailjetError):
                    unsent_employments.append(employments[index])
                    db.session.delete(employments[index])

        return [e for e in employments if not e in unsent_employments]


def review_employment(employment_id, reject):
    with atomic_transaction(commit_at_end=True):
        employment = Employment.query.get(employment_id)

        if not employment:
            raise AuthorizationError(
                "Actor is not authorized to review the employment"
            )

        employment.validate_by(current_user, reject=reject)

    return employment


class ValidateEmployment(AuthenticatedMutation):
    """
    Validation d'une invitation de rattachement par le salarié.

    Retourne le rattachement validé.
    """

    class Arguments:
        employment_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant du rattachement à valider",
        )

    Output = EmploymentOutput

    @classmethod
    @with_authorization_policy(active)
    def mutate(cls, _, info, employment_id):
        employment = review_employment(employment_id, reject=False)

        try:
            mailer.send_employment_validation_email(employment)
        except Exception as e:
            app.logger.exception(e)

        return employment


class RejectEmployment(AuthenticatedMutation):
    """
    Refus d'une invitation de rattachement par le salarié.

    Retourne le rattachement rejeté.
    """

    class Arguments:
        employment_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant du rattachement à refuser",
        )

    Output = EmploymentOutput

    @classmethod
    @with_authorization_policy(active)
    def mutate(cls, _, info, employment_id):
        return review_employment(employment_id, reject=True)


def _get_employment_by_token(token):
    employment = Employment.query.filter(
        Employment.invite_token == token
    ).one_or_none()

    if (
        not employment
        or employment.validation_status
        != EmploymentRequestValidationStatus.PENDING
        or employment.is_dismissed
    ):
        raise InvalidTokenError("Token does not match a valid employment")

    return employment


class GetInvitation(graphene.ObjectType):
    employment = graphene.Field(
        EmploymentOutput, token=graphene.String(required=True)
    )

    def resolve_employment(self, info, token):
        return _get_employment_by_token(token)


class RedeemInvitation(graphene.Mutation):
    class Arguments:
        token = graphene.Argument(graphene.String, required=True)

    Output = EmploymentOutput

    @classmethod
    def mutate(cls, _, info, token):
        user_to_auth = None
        with atomic_transaction(commit_at_end=True):
            employment = _get_employment_by_token(token)

            if employment.user:
                user_to_auth = employment.user
                employment.validate_by(user=user_to_auth)

            else:

                @require_auth_with_write_access
                def bind_and_redeem():
                    employment.bind(current_user)
                    employment.validate_by(user=current_user)

                bind_and_redeem()

        if user_to_auth:

            @after_this_request
            def set_cookies(response):
                set_auth_cookies(
                    response,
                    **create_access_tokens_for(user_to_auth),
                    user_id=user_to_auth.id,
                )
                return response

        return employment


class TerminateEmployment(AuthenticatedMutation):
    """
    Fin du rattachement d'un salarié.

    Retourne le rattachement.
    """

    class Arguments:
        employment_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant du rattachement à terminer",
        )
        end_date = graphene.Argument(
            graphene.Date,
            required=False,
            description="Date de fin du rattachement. Si non précisée, la date du jour sera utilisée.",
        )

    Output = EmploymentOutput

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: Employment.query.get(
            kwargs["employment_id"]
        ).company_id,
        error_message="Actor is not authorized to terminate the employment",
    )
    def mutate(cls, _, info, employment_id, end_date=None):
        with atomic_transaction(commit_at_end=True):
            employment_end_date = end_date or date.today()
            employment = Employment.query.get(employment_id)

            if current_user.id == employment.user_id:
                raise UserSelfTerminateEmploymentError

            if not employment.is_acknowledged or employment.end_date:
                raise EmploymentAlreadyTerminated(
                    f"Employment is inactive or has already an end date"
                )

            if employment.start_date > employment_end_date:
                raise InvalidParamsError(
                    "End date is before the employment start date"
                )

            if (
                query_activities(
                    user_id=employment.user_id,
                    start_time=employment_end_date + timedelta(days=1),
                    company_ids=[employment.company_id],
                ).count()
                > 0
            ):
                raise ActivityExistAfterEmploymentEndDate(
                    "User has logged activities for the company after this end date"
                )

            employment.end_date = employment_end_date

            db.session.add(employment)

        return employment


class CancelEmployment(AuthenticatedMutation):
    """
    Annulation du rattachement d'un salarié. Supprime le rattachement qu'il soit actif ou non.

    Retourne le rattachement
    """

    Output = Void

    class Arguments:
        employment_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant du rattachement à terminer",
        )

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: Employment.query.get(
            kwargs["employment_id"]
        ).company_id,
        error_message="Actor is not authorized to cancel the employment",
    )
    def mutate(self, _, info, employment_id):
        with atomic_transaction(commit_at_end=True):
            employment = Employment.query.get(employment_id)

            if employment.is_dismissed:
                raise InvalidResourceError(
                    f"Could not find valid employment with id {employment_id}"
                )

            employment.dismiss()

        return Void(success=True)


class SendInvitationReminder(AuthenticatedMutation):
    class Arguments:
        employment_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant du rattachement pour lequel relancer un email d'invitation",
        )

    Output = Void

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: Employment.query.get(
            kwargs["employment_id"]
        ).company_id,
        error_message="Actor is not authorized to send invitation emails for the employment",
    )
    def mutate(cls, _, info, employment_id):
        employment = Employment.query.get(employment_id)
        min_time_between_emails = app.config[
            "MIN_DELAY_BETWEEN_INVITATION_EMAILS"
        ]
        if (
            datetime.now()
            - (
                employment.latest_invite_email_time
                or employment.reception_time
            )
            >= min_time_between_emails
        ):
            mailer.send_employee_invite(employment, reminder=True)
            db.session.commit()

        return Void(success=True)


class ChangeEmployeeRole(AuthenticatedMutation):
    class Arguments:
        employment_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant du rattachement pour lequel le rôle doit être changé",
        )
        has_admin_rights = graphene.Argument(
            graphene.Boolean,
            required=True,
            description="Précise si le salarié rattaché est gestionnaire de l'entreprise, et s'il pourra donc avoir les droits de consultation et d'administration associés.",
        )

    Output = EmploymentOutput

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda *args, **kwargs: Employment.query.get(
            kwargs["employment_id"]
        ).company_id,
        error_message="Actor is not authorized to change employee role",
    )
    def mutate(cls, _, info, employment_id, has_admin_rights):
        employment = Employment.query.get(employment_id)
        if current_user.id == employment.user_id:
            raise UserSelfChangeRoleError
        employment.has_admin_rights = has_admin_rights
        db.session.commit()
        return employment
