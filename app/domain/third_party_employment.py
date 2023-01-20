import secrets
from datetime import datetime

from app import db
from app.helpers.errors import (
    EmploymentLinkNotFound,
    EmploymentLinkAlreadyAccepted,
    AuthorizationError,
    EmploymentLinkExpired,
)
from app.helpers.oauth.models import ThirdPartyClientEmployment


def generate_employment_token(client_employment_link):
    client_employment_link.access_token = secrets.token_hex(60)
    client_employment_link.invitation_token = None
    return client_employment_link


def create_third_party_employment_link_if_needed(employment_id, client_id):
    must_send_mail = False
    existing_link = ThirdPartyClientEmployment.query.filter(
        ThirdPartyClientEmployment.employment_id == employment_id,
        ThirdPartyClientEmployment.client_id == client_id,
        ~ThirdPartyClientEmployment.is_dismissed,
    ).one_or_none()
    if existing_link:
        if existing_link.access_token is None and existing_link.is_expired:
            existing_link.invitation_token = secrets.token_hex(60)
            existing_link.invitation_token_creation_time = datetime.now()
            must_send_mail = True
        return existing_link, must_send_mail

    invitation_token = secrets.token_hex(60)
    new_link = ThirdPartyClientEmployment(
        employment_id=employment_id,
        client_id=client_id,
        invitation_token=invitation_token,
    )
    must_send_mail = True
    db.session.add(new_link)
    return new_link, must_send_mail


def fetch_third_party_employment_link(
    client_id, employment_id, invitation_token
):
    client_employment_link = ThirdPartyClientEmployment.query.filter(
        ThirdPartyClientEmployment.employment_id == employment_id,
        ThirdPartyClientEmployment.client_id == client_id,
        ~ThirdPartyClientEmployment.is_dismissed,
    ).one_or_none()

    if not client_employment_link:
        raise EmploymentLinkNotFound

    if client_employment_link.access_token is not None:
        raise EmploymentLinkAlreadyAccepted

    if client_employment_link.invitation_token != invitation_token:
        raise AuthorizationError

    if client_employment_link.is_expired:
        raise EmploymentLinkExpired

    return client_employment_link
