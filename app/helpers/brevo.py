from __future__ import print_function
from typing import NamedTuple

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from app import app
from app.helpers.errors import MobilicError

BREVO_COMPANY_SUBSCRIBE_LIST = 19


class BrevoRequestError(MobilicError):
    code = "BREVO_API_ERROR"
    default_message = "Request to Brevo API failed"


class CreateContactData(NamedTuple):
    email: str
    admin_last_name: str
    admin_first_name: str
    company_name: str
    siren: int


class BrevoApiClient:
    def __init__(self, api_key):
        self._configuration = sib_api_v3_sdk.Configuration()
        self._configuration.api_key["api-key"] = api_key

        self._api_instance = sib_api_v3_sdk.ContactsApi(
            sib_api_v3_sdk.ApiClient(self._configuration)
        )

    def create_contact(self, data: CreateContactData):
        try:
            create_contact = sib_api_v3_sdk.CreateContact(
                email=data.email,
                update_enabled=True,
                attributes={
                    "NOM": data.admin_last_name,
                    "PRENOM": data.admin_first_name,
                    "SIREN": data.siren,
                    "NOM_ENTREPRISE": data.company_name,
                },
                list_ids=[BREVO_COMPANY_SUBSCRIBE_LIST],
            )
            api_response = self._api_instance.create_contact(create_contact)
            print(api_response)
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")


brevo = BrevoApiClient(app.config["BREVO_API_KEY"])
