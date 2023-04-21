from enum import Enum

from app import db
from app.models import Company, CompanyCertification


class SirenRegistrationStatus(str, Enum):
    UNREGISTERED = "unregistered"
    FULLY_REGISTERED = "fully_registered"
    PARTIALLY_REGISTERED = "partially_registered"


def get_siren_registration_status(siren):
    all_registered_companies_for_siren = Company.query.filter(
        Company.siren == siren
    ).all()

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
