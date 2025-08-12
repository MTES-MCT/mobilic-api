import datetime
from enum import Enum

from sqlalchemy import desc, asc, nullsfirst
from sqlalchemy import exists, and_
from sqlalchemy import func, or_
from sqlalchemy.sql.functions import now
from sqlalchemy.orm import joinedload

from app import db, siren_api_client, app
from app.helpers.mail_type import EmailType
from app.jobs import log_execution
from app.models import Company, CompanyCertification, UserAgreement
from app.models import (
    Employment,
    Email,
    Mission,
    Activity,
)
from app.models.company_certification import (
    CERTIFICATION_ADMIN_CHANGES_BRONZE,
    CERTIFICATION_REAL_TIME_BRONZE,
)
from app.models.employment import EmploymentRequestValidationStatus
from app.models.user_agreement import UserAgreementStatus

AT_LEAST_BRONZE_FILTER = and_(
    CompanyCertification.admin_changes <= CERTIFICATION_ADMIN_CHANGES_BRONZE,
    CompanyCertification.log_in_real_time >= CERTIFICATION_REAL_TIME_BRONZE,
)


class SirenRegistrationStatus(str, Enum):
    UNREGISTERED = "unregistered"
    FULLY_REGISTERED = "fully_registered"
    PARTIALLY_REGISTERED = "partially_registered"


def get_siren_registration_status(siren):
    all_registered_companies_for_siren = get_companies_by_siren(siren)

    if not all_registered_companies_for_siren:
        return SirenRegistrationStatus.UNREGISTERED, None
    if any(
        [c.short_sirets is None for c in all_registered_companies_for_siren]
    ):
        return SirenRegistrationStatus.FULLY_REGISTERED, None
    registered_sirets = []
    for c in all_registered_companies_for_siren:
        if c.short_sirets:
            registered_sirets.extend(c.short_sirets)
    return SirenRegistrationStatus.PARTIALLY_REGISTERED, registered_sirets


def link_company_to_software(company_id, client_id):
    from app.helpers.oauth.models import ThirdPartyClientCompany

    existing_link = ThirdPartyClientCompany.query.filter(
        ThirdPartyClientCompany.company_id == company_id,
        ThirdPartyClientCompany.client_id == client_id,
        ~ThirdPartyClientCompany.is_dismissed,
    ).one_or_none()
    if existing_link:
        return existing_link
    new_link = ThirdPartyClientCompany(
        client_id=client_id, company_id=company_id
    )
    db.session.add(new_link)
    return new_link


def change_company_certification_communication_pref(company_ids, accept):
    Company.query.filter(Company.id.in_(company_ids)).update(
        {"accept_certification_communication": accept},
        synchronize_session=False,
    )


def get_last_day_of_certification(company_id):
    return (
        db.session.query(db.func.max(CompanyCertification.expiration_date))
        .filter(
            CompanyCertification.company_id == company_id,
            AT_LEAST_BRONZE_FILTER,
        )
        .first()
    )[0]


def get_current_certificate(company_id):
    certifications = CompanyCertification.query.filter(
        CompanyCertification.company_id == company_id,
        AT_LEAST_BRONZE_FILTER,
        CompanyCertification.expiration_date >= datetime.datetime.now().date(),
    ).all()
    if len(certifications) == 0:
        return None

    certifications.sort(key=lambda c: c.attribution_date, reverse=True)
    certifications.sort(key=lambda c: c.certification_level, reverse=True)
    return certifications[0]


def get_start_last_certification_period(company_id):
    start_last_certification_period = None
    certifications = (
        CompanyCertification.query.filter(
            CompanyCertification.company_id == company_id,
            AT_LEAST_BRONZE_FILTER,
        )
        .order_by(desc(CompanyCertification.attribution_date))
        .all()
    )
    for certification in certifications:
        if (
            start_last_certification_period is None
            or start_last_certification_period
            <= certification.expiration_date + datetime.timedelta(days=1)
        ):
            start_last_certification_period = certification.attribution_date
        else:
            break
    return start_last_certification_period


def get_company_by_siret(siret):
    all_registered_companies_for_siren = get_companies_by_siren(siret[:9])
    for c in all_registered_companies_for_siren:
        if c.short_sirets:
            for short_siret in c.short_sirets:
                if str(short_siret).zfill(5) == siret[9:]:
                    # Return the company corresponding to the specific siret
                    return c
        else:
            # Return the company corresponding to the whole SIREN organization
            return c
    return None


def get_companies_by_siren(siren):
    return Company.query.filter(Company.siren == siren).all()


def find_companies_by_name(company_name):
    return Company.query.filter(
        or_(
            func.translate(Company.usual_name, " .-", "").ilike(
                f"{company_name}%"
            ),
            func.translate(Company.usual_name, ".-", " ").ilike(
                f"% {company_name}%"
            ),
        )
    ).all()


def find_certified_companies_query():
    return (
        db.session.query(
            Company.id,
            Company.usual_name,
            Company.siren,
            Company.short_sirets,
            func.max(CompanyCertification.expiration_date).label(
                "expiration_date"
            ),
        )
        .group_by(
            Company.id, Company.usual_name, Company.siren, Company.short_sirets
        )
        .join(
            CompanyCertification, CompanyCertification.company_id == Company.id
        )
        .filter(
            Company.accept_certification_communication,
            AT_LEAST_BRONZE_FILTER,
            CompanyCertification.expiration_date > now(),
        )
    )


def check_company_has_no_activities(company_id):
    exists_activity_query = db.session.query(
        exists().where(
            and_(
                Activity.mission_id == Mission.id,
                Mission.company_id == company_id,
                ~Activity.is_dismissed,
            )
        )
    )
    return not db.session.scalar(exists_activity_query)


def apply_business_type_to_company_employees(company, new_business):
    company_employments = company.employments
    for employment in company_employments:
        employment.business = new_business
    db.session.flush()


def has_any_active_admin(company):
    admins = company.get_admins(
        start=datetime.date.today(), end=datetime.date.today()
    )
    if len(admins) == 0:
        return False

    blacklisted_admins = UserAgreement.query.filter(
        UserAgreement.user_id.in_([admin.id for admin in admins]),
        UserAgreement.status == UserAgreementStatus.REJECTED,
    ).all()

    return len(admins) > len(blacklisted_admins)


def _get_companies_without_any_employee():
    return Company.query.filter(
        ~exists().where(
            and_(
                Employment.company_id == Company.id,
                Employment.has_admin_rights == False,
            )
        )
    ).all()


def find_admins_of_companies_without_any_employee_invitations(
    company_creation_trigger_date, companies_to_exclude=None
):

    companies_without_any_employee = _get_companies_without_any_employee()

    return Employment.query.filter(
        Employment.company.has(
            Company.creation_time
            <= datetime.datetime.combine(
                company_creation_trigger_date, datetime.datetime.max.time()
            )
        ),
        ~exists().where(
            and_(
                Email.employment_id == Employment.id,
                Email.type.in_(
                    [
                        EmailType.COMPANY_WITHOUT_ANY_INVITATION,
                        EmailType.COMPANY_NEVER_ACTIVE,
                    ]
                ),
            )
        ),
        Employment.company_id.notin_(companies_to_exclude or []),
        Employment.company_id.in_(
            [company.id for company in companies_without_any_employee]
        ),
        Employment.has_admin_rights,
        ~Employment.is_dismissed,
        Employment.end_date.is_(None),
        Employment.validation_status
        == EmploymentRequestValidationStatus.APPROVED,
    ).all()


def find_admins_of_companies_with_an_employee_but_without_any_activity(
    first_employee_invitation_date, companies_to_exclude=None
):

    companies_with_no_activities_and_with_at_least_one_employee_before_trigger_date = Company.query.filter(
        ~exists().where(Mission.company_id == Company.id),
        exists().where(
            and_(
                Employment.company_id == Company.id,
                Employment.has_admin_rights == False,
                Employment.creation_time
                <= datetime.datetime.combine(
                    first_employee_invitation_date,
                    datetime.datetime.max.time(),
                ),
            )
        ),
    ).all()

    return Employment.query.filter(
        ~exists().where(
            and_(
                Email.employment_id == Employment.id,
                Email.type.in_(
                    [
                        EmailType.COMPANY_WITH_EMPLOYEE_BUT_WITHOUT_ACTIVITY,
                        EmailType.COMPANY_NEVER_ACTIVE,
                    ]
                ),
            )
        ),
        Employment.company_id.notin_(companies_to_exclude or []),
        Employment.has_admin_rights,
        ~Employment.is_dismissed,
        Employment.end_date.is_(None),
        Employment.validation_status
        == EmploymentRequestValidationStatus.APPROVED,
        Employment.company_id.in_(
            [
                company.id
                for company in companies_with_no_activities_and_with_at_least_one_employee_before_trigger_date
            ]
        ),
    ).all()


def find_admins_still_without_invitations(
    received_first_email_before_date, companies_to_exclude=None
):
    companies_without_any_employee = _get_companies_without_any_employee()

    return Employment.query.filter(
        ~exists().where(
            and_(
                Email.employment_id == Employment.id,
                Email.type == EmailType.COMPANY_REMINDER_NO_INVITATION,
            )
        ),
        exists().where(
            and_(
                Email.employment_id == Employment.id,
                Email.type == EmailType.COMPANY_WITHOUT_ANY_INVITATION,
                Email.creation_time
                <= datetime.datetime.combine(
                    received_first_email_before_date,
                    datetime.datetime.max.time(),
                ),
            )
        ),
        Employment.company_id.notin_(companies_to_exclude or []),
        Employment.company_id.in_(
            [company.id for company in companies_without_any_employee]
        ),
        Employment.has_admin_rights,
        ~Employment.is_dismissed,
        Employment.end_date.is_(None),
        Employment.validation_status
        == EmploymentRequestValidationStatus.APPROVED,
    ).all()


def find_employee_for_invitation(
    first_employee_invitation_date,
    max_start_date=None,
    companies_to_exclude=None,
):
    scheduled_invitations = (
        db.session.query(Email.address)
        .filter(Email.type == EmailType.SCHEDULED_INVITATION)
        .subquery()
    )

    base_query = (
        db.session.query(Employment)
        .options(joinedload(Employment.company))
        .join(Email, Email.address == Employment.email)
        .distinct(Email.address)
        .filter(
            Email.type == EmailType.INVITATION,
            Email.user_id.is_(None),
            Email.creation_time
            <= datetime.datetime.combine(
                first_employee_invitation_date,
                datetime.datetime.max.time(),
            ),
            Employment.has_admin_rights == False,
            Employment.user_id.is_(None),
            Employment.validation_status
            == EmploymentRequestValidationStatus.PENDING,
            ~Employment.email.in_(scheduled_invitations),
        )
    )
    if companies_to_exclude:
        base_query = base_query.filter(
            Employment.company_id.notin_(companies_to_exclude)
        )
    if max_start_date:
        base_query = base_query.filter(
            Employment.creation_time
            >= datetime.datetime.combine(
                max_start_date, datetime.datetime.min.time()
            )
        )

    query = base_query.order_by(Email.address, Email.creation_time.desc())

    return query.yield_per(100).all()


def find_admins_with_pending_invitation(
    pending_invitation_trigger_date,
    companies_to_exclude=None,
):
    # Get companies that have scheduled invitations and invitations still in pending before the trigger date
    scheduled_invitations = (
        db.session.query(Employment.company_id)
        .join(Email, Email.address == Employment.email)
        .filter(
            Email.type == EmailType.SCHEDULED_INVITATION,
            Email.creation_time
            <= datetime.datetime.combine(
                pending_invitation_trigger_date,
                datetime.datetime.max.time(),
            ),
            Employment.has_admin_rights == False,
            Employment.user_id.is_(None),
            Employment.validation_status
            == EmploymentRequestValidationStatus.PENDING,
        )
        .distinct()
        .subquery()
    )

    # Get employments that have already received the pending invitation email
    second_scheduled_invitations = (
        db.session.query(Email.employment_id)
        .filter(Email.type == EmailType.COMPANY_PENDING_INVITATION)
        .distinct()
        .subquery()
    )

    # Base query to find employments that are admins and have not received the pending invitation email
    base_query = (
        db.session.query(Employment)
        .options(joinedload(Employment.company))
        .filter(
            Employment.company_id.in_(scheduled_invitations),
            ~Employment.id.in_(second_scheduled_invitations),
            Employment.has_admin_rights == True,
            Employment.user_id.isnot(None),
            ~Employment.is_dismissed,
            Employment.end_date.is_(None),
            Employment.validation_status
            == EmploymentRequestValidationStatus.APPROVED,
        )
    )
    if companies_to_exclude:
        base_query = base_query.filter(
            Employment.company_id.notin_(companies_to_exclude)
        )

    return base_query.yield_per(100).all()


@log_execution
def job_update_ceased_activity_status():

    companies = (
        Company.query.filter(
            Company.has_ceased_activity == False, Company.siren.isnot(None)
        )
        .order_by(nullsfirst(asc(Company.siren_api_info_last_update)))
        .limit(100)
    )

    for company in companies:
        (
            has_ceased_activity,
            siren_info,
        ) = siren_api_client.has_company_ceased_activity(company.siren)
        if has_ceased_activity:
            app.logger.info(f"{company} has ceased activity...")

            employments = Employment.query.filter(
                Employment.company_id == company.id,
                ~Employment.is_dismissed,
                Employment.end_date.is_(None),
                Employment.validation_status.in_(
                    [
                        EmploymentRequestValidationStatus.PENDING,
                        EmploymentRequestValidationStatus.APPROVED,
                    ]
                ),
            ).all()

            app.logger.info(
                f"#{len(employments)} employments will be terminated or dismissed"
            )

            for employment in employments:
                if (
                    employment.validation_status
                    == EmploymentRequestValidationStatus.APPROVED
                ):
                    employment.end_date = (
                        datetime.date.today() - datetime.timedelta(days=1)
                    )
                elif (
                    employment.validation_status
                    == EmploymentRequestValidationStatus.PENDING
                ):
                    db.session.delete(employment)

            company.has_ceased_activity = True

        company.siren_api_info = siren_info
        db.session.commit()
