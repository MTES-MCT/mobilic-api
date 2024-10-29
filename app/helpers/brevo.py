import time
from functools import wraps
from dataclasses import dataclass
from typing import Optional

import requests
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from app import app
from app.helpers.errors import MobilicError


class BrevoRequestError(MobilicError):
    code = "BREVO_API_ERROR"
    default_message = "Request to Brevo API failed"


@dataclass
class CreateContactData:
    email: str
    admin_last_name: str
    admin_first_name: str
    company_name: str
    siren: int
    phone_number: Optional[str] = None


@dataclass
class CreateCompanyData:
    company_name: str
    siren: int
    phone_number: Optional[str] = None


@dataclass
class LinkCompanyContactData:
    company_id: int
    contact_id: int


@dataclass
class GetCompanyData:
    company_id: str


@dataclass
class GetDealData:
    deal_id: str


@dataclass
class UpdateDealStageData:
    deal_id: str
    pipeline_id: str
    stage_id: str


@dataclass
class GetAllDealsByPipelineData:
    pipeline_id: str


def check_api_key(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.api_key is None:
            app.logger.warning("BREVO_API_KEY not found.")
            return None
        else:
            return func(self, *args, **kwargs)

    return wrapper


class BrevoApiClient:
    BASE_URL = "https://api.brevo.com/v3/"

    def __init__(self, api_key):
        self._configuration = sib_api_v3_sdk.Configuration()
        self._configuration.api_key["api-key"] = api_key
        self.api_key = api_key
        self._api_instance = sib_api_v3_sdk.ContactsApi(
            sib_api_v3_sdk.ApiClient(self._configuration)
        )

        self._session = requests.Session()
        self._session.headers.update(
            {
                "api-key": api_key,
                "accept": "application/json",
                "content-type": "application/json",
            }
        )

    @check_api_key
    def create_contact(self, data: CreateContactData):
        try:
            attributes = {
                "NOM": data.admin_last_name,
                "PRENOM": data.admin_first_name,
                "SIREN": data.siren,
                "NOM_ENTREPRISE": data.company_name,
            }

            if data.phone_number:
                attributes["SMS"] = self.remove_plus_sign(data.phone_number)

            create_contact = sib_api_v3_sdk.CreateContact(
                email=data.email,
                update_enabled=True,
                attributes=attributes,
                list_ids=[BREVO_COMPANY_SUBSCRIBE_LIST],
            )
            api_response = self._api_instance.create_contact(create_contact)
            return api_response.id
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def create_company(self, data: CreateCompanyData):
        try:
            url = f"{self.BASE_URL}companies"
            attributes = {
                "activation_mobilic": "Inscrite",
                "siren": data.siren,
                "owner": "Pathtech PATHTECH",
            }

            if data.phone_number:
                attributes["phone_number"] = self.remove_plus_sign(
                    data.phone_number
                )

            create_company_payload = {
                "name": data.company_name,
                "attributes": attributes,
            }
            response = self._session.post(url, json=create_company_payload)
            response.raise_for_status()
            return response.json()["id"]
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def link_company_and_contact(self, data: LinkCompanyContactData):
        try:
            url = f"{self.BASE_URL}companies/link-unlink/{data.company_id}"
            payload = {"linkContactIds": [data.contact_id]}
            response = self._session.patch(url, json=payload)
            return response
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def get_company(self, data: GetCompanyData):
        try:
            url = f"{self.BASE_URL}/companies/{data.company_id}"
            response = self._session.get(url)
            response.raise_for_status()
            return response.json()
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def get_deal(self, data: GetDealData):
        try:
            url = f"{self.BASE_URL}crm/deals/{data.deal_id}"
            response = self._session.get(url)
            response.raise_for_status()
            return response.json()
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def update_deal_stage(self, data: UpdateDealStageData):
        try:
            url = f"{self.BASE_URL}crm/deals/{data.deal_id}"
            payload = {
                "attributes": {
                    "pipeline": data.pipeline_id,
                    "deal_stage": data.stage_id,
                }
            }
            response = self._session.patch(url, json=payload)
            response.raise_for_status()

            if response.status_code == 204:
                return {"message": "Deal stage updated successfully"}

            return response.json()
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def get_all_deals_by_pipeline(self, data: GetAllDealsByPipelineData):
        try:
            all_deals = []
            offset = 0
            limit = 100  # Brevo's maximum limit per request (https://developers.brevo.com/docs/api-limits#general-rate-limiting)

            while True:
                params = {
                    "filters[attributes.pipeline]": data.pipeline_id,
                    "offset": offset,
                    "limit": limit,
                }

                response = self._session.get(
                    f"{self.BASE_URL}crm/deals", params=params
                )
                # Retry after delay if rate-limited (https://developers.brevo.com/docs/api-limits#rate-limit-reset)
                if response.status_code == 429:
                    time.sleep(
                        int(response.headers.get("x-sib-ratelimit-reset", 1))
                    )
                    continue

                response.raise_for_status()
                deals = response.json().get("items", [])
                if not deals:
                    break

                all_deals.extend(deals)
                offset += limit

            return {"items": all_deals}
        except requests.exceptions.RequestException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def get_all_pipelines(self):
        try:
            url = f"{self.BASE_URL}crm/pipeline/details/all"
            response = self._session.get(url)
            response.raise_for_status()
            return response.json()
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def get_pipeline_details(self, pipeline_id: str):
        try:
            url = f"{self.BASE_URL}crm/pipeline/details/{pipeline_id}"
            response = self._session.get(url)
            response.raise_for_status()
            return response.json()
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def get_stage_name(self, pipeline_id: str, stage_id: str):
        pipeline_details = self.get_pipeline_details(pipeline_id)

        if isinstance(pipeline_details, list):
            pipeline = next(
                (
                    item
                    for item in pipeline_details
                    if item.get("pipeline") == pipeline_id
                ),
                None,
            )
            if not pipeline:
                app.logger.warning(
                    f"Pipeline with ID {pipeline_id} not found."
                )
                return None
        else:
            pipeline = pipeline_details

        stages = pipeline.get("stages", [])
        for stage in stages:
            if stage["id"] == stage_id:
                return stage["name"]

        app.logger.warning(
            f"Stage with ID {stage_id} not found in pipeline {pipeline_id}."
        )
        return None

    @staticmethod
    def remove_plus_sign(phone_number):
        if phone_number.startswith("+"):
            return phone_number[1:]
        return phone_number


# list number 19  is for prod only : https://app.brevo.com/contact/list/id/19
# use list number 22 for testing purpose : https://app.brevo.com/contact/list/id/22
try:
    BREVO_COMPANY_SUBSCRIBE_LIST = int(
        app.config["BREVO_COMPANY_SUBSCRIBE_LIST"]
    )
except (ValueError, TypeError):
    raise ValueError("BREVO_COMPANY_SUBSCRIBE_LIST must be an integer")

brevo = BrevoApiClient(app.config["BREVO_API_KEY"])
