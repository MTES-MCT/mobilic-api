from enum import Enum

from sqlalchemy import func, or_, desc
from sqlalchemy.sql.functions import now

from app import db
from app.models import Company, CompanyCertification


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
            CompanyCertification.be_active,
            CompanyCertification.be_compliant,
            CompanyCertification.not_too_many_changes,
            CompanyCertification.validate_regularly,
            CompanyCertification.log_in_real_time,
        )
        .first()
    )[0]


def get_start_last_certification_period(company_id):
    start_last_certification_period = None
    certifications = (
        CompanyCertification.query.filter(
            CompanyCertification.company_id == company_id,
            CompanyCertification.be_active,
            CompanyCertification.be_compliant,
            CompanyCertification.not_too_many_changes,
            CompanyCertification.validate_regularly,
            CompanyCertification.log_in_real_time,
        )
        .order_by(desc(CompanyCertification.attribution_date))
        .all()
    )
    for certification in certifications:
        if (
            start_last_certification_period is None
            or start_last_certification_period <= certification.expiration_date
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
            CompanyCertification.be_active,
            CompanyCertification.be_compliant,
            CompanyCertification.not_too_many_changes,
            CompanyCertification.validate_regularly,
            CompanyCertification.log_in_real_time,
            CompanyCertification.expiration_date > now(),
        )
    )
