from flask import after_this_request

from app.domain.permissions import company_admin_at
from app.helpers.authentication import (
    current_user,
    set_auth_cookies,
    create_access_tokens_for,
)
import graphene
from datetime import datetime, date
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, DatabaseError
from uuid import uuid4

from app import app, db, mailer
from app.controllers.utils import atomic_transaction
from app.helpers.errors import (
    MissingPrimaryEmploymentError,
    InvalidParamsError,
    OverlappingEmploymentsError,
    InternalError,
    InvalidTokenError,
    InvalidResourceError,
)
from app.helpers.authentication import AuthenticationError
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated_and_active,
    AuthorizationError,
)
from app.models import Company, User
from app.models.employment import (
    EmploymentOutput,
    Employment,
    EmploymentRequestValidationStatus,
)


class CreateEmployment(graphene.Mutation):
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
            description="Précise si le salarié rattaché est gestionnaire de l'entreprise, et s'il pourra donc avoir les droits de consultation et d'admnistration associés. Par défaut, si l'argument n'est pas présent le salarié n'aura pas les droits.",
        )
        is_primary = graphene.Argument(
            graphene.Boolean,
            required=False,
            description="Précise si l'entreprise de rattachement est l'entreprise principale du travailleur. Un salarié ne peut pas être rattaché à deux entreprises principales en même temps mais il peut avoir plusieurs rattachements secondaires, qui lui permettront d'associer du temps de travail à ces entreprises. Par défaut le rattachement est considéré comme principal",
        )

    Output = EmploymentOutput

    @classmethod
    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
    )
    def mutate(cls, _, info, **employment_input):
        try:
            with atomic_transaction(commit_at_end=True):
                reception_time = datetime.now()
                app.logger.info(
                    f"Creating employment submitted by {current_user} for User {employment_input.get('user_id', employment_input.get('mail'))} in Company {employment_input['company_id']}"
                )
                company = Company.query.get(employment_input["company_id"])

                if (employment_input.get("user_id") is None) == (
                    employment_input.get("mail") is None
                ):
                    raise InvalidParamsError(
                        "Exactly one of userId or mail should be provided."
                    )

                user_id = employment_input.get("user_id")
                user = None
                invite_token = uuid4().hex
                if user_id:
                    user = User.query.options(
                        selectinload(User.employments)
                    ).get(employment_input["user_id"])
                    if not user:
                        raise InvalidResourceError("Invalid user id")

                start_date = employment_input.get("start_date", date.today())

                if user:
                    user_current_primary_employment = (
                        user.primary_employment_at(start_date)
                        if user
                        else None
                    )
                    if (
                        not user_current_primary_employment
                        and not employment_input.get("is_primary", True)
                    ):
                        raise MissingPrimaryEmploymentError(
                            "Cannot create a secondary employment for user because there is no primary employment in the same period"
                        )

                employment = Employment(
                    reception_time=reception_time,
                    submitter=current_user,
                    is_primary=employment_input.get("is_primary", True),
                    validation_status=EmploymentRequestValidationStatus.PENDING,
                    start_date=start_date,
                    end_date=employment_input.get("end_date"),
                    company=company,
                    has_admin_rights=employment_input.get("has_admin_rights"),
                    user_id=user_id,
                    invite_token=invite_token,
                    email=employment_input.get("mail"),
                )
                db.session.add(employment)

        except IntegrityError as e:
            app.logger.exception(e)
            raise OverlappingEmploymentsError(e)

        except DatabaseError as e:
            app.logger.exception(e)
            raise InternalError("An internal error occurred")

        try:
            mailer.send_employee_invite(
                employment,
                user.email if user else employment_input.get("mail"),
            )
        except Exception as e:
            app.logger.exception(e)

        return employment


def review_employment(employment_id, reject):
    with atomic_transaction(commit_at_end=True):
        employment = Employment.query.get(employment_id)

        if not employment:
            raise AuthorizationError(
                "Actor is not authorized to review the employment"
            )

        employment.validate_by(current_user, reject=reject)

    return employment


class ValidateEmployment(graphene.Mutation):
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
    @with_authorization_policy(authenticated_and_active)
    def mutate(cls, _, info, employment_id):
        employment = review_employment(employment_id, reject=False)

        try:
            mailer.send_employment_validation_email(employment)
        except Exception as e:
            app.logger.exception(e)

        return employment


class RejectEmployment(graphene.Mutation):
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
    @with_authorization_policy(authenticated_and_active)
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
        try:
            with atomic_transaction(commit_at_end=True):
                employment = _get_employment_by_token(token)

                if employment.user:
                    user_to_auth = employment.user
                    employment.validate_by(user=user_to_auth)

                else:

                    @with_authorization_policy(authenticated_and_active)
                    def bind_and_redeem():
                        employment.user_id = current_user.id
                        employment.validate_by(user=current_user)

                    bind_and_redeem()

        except IntegrityError as e:
            app.logger.exception(e)
            raise OverlappingEmploymentsError(e)

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


class TerminateEmployment(graphene.Mutation):
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
    @with_authorization_policy(authenticated_and_active)
    def mutate(cls, _, info, employment_id, end_date=None):
        with atomic_transaction(commit_at_end=True):
            employment_end_date = end_date or date.today()

            employment = Employment.query.get(employment_id)
            if not employment or not company_admin_at(
                current_user, employment.company
            ):
                raise AuthorizationError(
                    "Actor is not authorized to terminate the employment"
                )

            if not employment.is_acknowledged or employment.end_date:
                raise InvalidResourceError(
                    f"Employment is inactive or has already an end date"
                )

            if employment.start_date > employment_end_date:
                raise InvalidParamsError(
                    "End date is before the employment start date"
                )

            app.logger.info(
                f"Terminating employment for User {employment.user_id} in Company {employment.company_id}"
            )
            employment.end_date = employment_end_date

            db.session.add(employment)

        return employment


class CancelEmployment(graphene.Mutation):
    """
    Annulation du rattachement d'un salarié. Supprime le rattachement qu'il soit actif ou non.

    Retourne le rattachement
    """

    message = graphene.String()

    class Arguments:
        employment_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant du rattachement à terminer",
        )

    @classmethod
    @with_authorization_policy(authenticated_and_active)
    def mutate(self, _, info, employment_id):
        with atomic_transaction(commit_at_end=True):
            employment = Employment.query.get(employment_id)

            if not employment or not company_admin_at(
                current_user, employment.company
            ):
                raise AuthorizationError(
                    "Actor is not authorized to cancel the employment"
                )

            if employment.is_dismissed:
                raise InvalidResourceError(
                    f"Could not find valid employment with id {employment_id}"
                )
            app.logger.info(f"Cancelling Employment {employment_id}")

            employment.dismiss()

        return CancelEmployment(message="success")
