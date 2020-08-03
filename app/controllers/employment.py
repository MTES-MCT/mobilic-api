from app.domain.permissions import company_admin_at
from app.helpers.authentication import current_user
import graphene
from datetime import datetime, date
from sqlalchemy.orm import selectinload
from uuid import uuid4

from app import app, db, mailer
from app.controllers.utils import atomic_transaction
from app.helpers.errors import (
    MissingPrimaryEmploymentError,
    EmploymentAlreadyReviewedByUserError,
    InvalidParamsError,
    EmploymentNotFoundError,
)
from app.helpers.authorization import with_authorization_policy, authenticated
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
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            app.logger.info(
                f"Creating employment submitted by {current_user} for User {employment_input.get('user_id', employment_input.get('mail'))} in Company {employment_input['company_id']}"
            )
            company = Company.query.get(employment_input["company_id"])

            if employment_input.get("user_id") == employment_input.get("mail"):
                raise InvalidParamsError(
                    "Exactly one of user_id or mail should be provided."
                )

            user_id = employment_input.get("user_id")
            user = None
            invite_token = None
            if user_id:
                user = User.query.options(selectinload(User.employments)).get(
                    employment_input["user_id"]
                )

            if employment_input.get("mail"):
                invite_token = uuid4().hex

            start_date = employment_input.get("start_date", date.today())

            if user:
                user_current_primary_employment = (
                    user.primary_employment_at(start_date) if user else None
                )
                if (
                    not user_current_primary_employment
                    and not employment_input.get("is_primary", True)
                ):
                    raise MissingPrimaryEmploymentError(
                        f"Cannot create a secondary employment for {user} because there is no primary employment in the same period"
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
            db.session.flush()

            if invite_token:
                try:
                    mailer.send_employee_invite(
                        employment, employment_input.get("mail")
                    )
                except Exception as e:
                    app.logger.exception(e)

        return employment


def review_employment(employment_id, reject):
    with atomic_transaction(commit_at_end=True):
        employment = None
        try:
            employment = Employment.query.get(employment_id)
        except Exception as e:
            pass

        if not employment:
            raise EmploymentAlreadyReviewedByUserError(
                f"Could not find pending Employment event with id {employment_id}"
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
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, employment_id):
        return review_employment(employment_id, reject=False)


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
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, employment_id):
        return review_employment(employment_id, reject=True)


def _get_employment_by_token(token):
    employment = Employment.query.filter(
        Employment.invite_token == token
    ).one_or_none()

    if not employment or employment.user_id:
        raise EmploymentNotFoundError(
            f"Could not find a valid employment not bound to a user for token {token}"
        )

    return employment


class GetInvitation(graphene.ObjectType):
    employment = graphene.Field(
        EmploymentOutput, invite_token=graphene.String(required=True)
    )

    def resolve_employment(self, info, invite_token):
        return _get_employment_by_token(invite_token)


class RedeemInvitation(graphene.Mutation):
    class Arguments:
        invite_token = graphene.Argument(graphene.String, required=True)

    Output = EmploymentOutput

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, invite_token):
        with atomic_transaction(commit_at_end=True):
            employment = _get_employment_by_token(invite_token)
            print(current_user)
            employment.user_id = current_user.id

        return employment
