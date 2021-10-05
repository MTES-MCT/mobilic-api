from enum import Enum

from app.models import Company


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
