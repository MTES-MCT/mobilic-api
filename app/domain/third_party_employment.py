import secrets

from app import db
from app.helpers.oauth.models import ThirdPartyClientEmployment


def generate_employment_token(client_employment_link):
    client_employment_link.access_token = secrets.token_hex(60)
    client_employment_link.invitation_token = None
    return client_employment_link


def create_third_party_employment_link_if_needed(employment_id, client_id):
    existing_link = ThirdPartyClientEmployment.query.filter(
        ThirdPartyClientEmployment.employment_id == employment_id,
        ThirdPartyClientEmployment.client_id == client_id,
        ~ThirdPartyClientEmployment.is_dismissed,
    ).one_or_none()
    if existing_link:
        return existing_link

    invitation_token = secrets.token_hex(60)
    new_link = ThirdPartyClientEmployment(
        employment_id=employment_id,
        client_id=client_id,
        invitation_token=invitation_token,
    )
    # TODO : Envoyer mail pour que le salarié puisse générer son token
    db.session.add(new_link)
    return new_link
