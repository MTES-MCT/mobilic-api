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
    siren: str
    phone_number: Optional[str] = None


@dataclass
class CreateCompanyData:
    company_name: str
    siren: str
    siret: Optional[str] = None
    phone_number: Optional[str] = None


@dataclass
class LinkCompanyContactData:
    company_id: int
    contact_id: int


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
    BASE_URL = "https://api.brevo.com/v3"

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

        self._companies_cache = None

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
            url = f"{self.BASE_URL}/companies"
            attributes = {
                "activation_mobilic": "Inscrite",
                "siren": data.siren,
                "owner": "Pathtech PATHTECH",
            }

            if data.siret:
                attributes["siret"] = data.siret

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
            url = f"{self.BASE_URL}/companies/link-unlink/{data.company_id}"
            payload = {"linkContactIds": [data.contact_id]}
            response = self._session.patch(url, json=payload)
            response.raise_for_status()
            return response
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def update_deal_stage(self, data: UpdateDealStageData):
        try:
            url = f"{self.BASE_URL}/crm/deals/{data.deal_id}"
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
            limit = 10000
            # Brevo's maximum request limit per hour request (https://developers.brevo.com/docs/api-limits#general-rate-limiting)
            max_attempts = 100

            for _ in range(max_attempts):
                params = {
                    "filters[attributes.pipeline]": data.pipeline_id,
                    "offset": offset,
                    "limit": limit,
                }

                response = self._session.get(
                    f"{self.BASE_URL}/crm/deals", params=params
                )
                # Retry after delay if rate-limited (https://developers.brevo.com/docs/api-limits#rate-limit-reset)
                if response.status_code == 429:
                    app.logger.warning("Rate limit exceeded. Stopping batch.")
                    break

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
            url = f"{self.BASE_URL}/crm/pipeline/details/all"
            response = self._session.get(url)
            response.raise_for_status()
            return response.json()
        except ApiException as e:
            raise BrevoRequestError(f"Request to Brevo API failed: {e}")

    @check_api_key
    def get_pipeline_details(self, pipeline_id: str):
        try:
            url = f"{self.BASE_URL}/crm/pipeline/details/{pipeline_id}"
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

    @check_api_key
    def get_deal_attributes(self):
        try:
            url = f"{self.BASE_URL}/crm/attributes/deals"
            response = self._session.get(url)
            response.raise_for_status()
            result = response.json()
            app.logger.debug(f"Deal attributes response: {result}")
            return result
        except Exception as e:
            app.logger.error(f"Failed to get deal attributes: {e}")
            return {}

    @check_api_key
    def create_deal_with_attributes(
        self, company_data: dict, pipeline_id: str, stage_id: str, status: str
    ) -> str:
        """Create a new deal in Brevo with company attributes.

        Args:
            company_data: Dictionary containing company information
            pipeline_id: Brevo pipeline identifier
            stage_id: Brevo stage identifier within the pipeline
            status: Deal status description

        Returns:
            Deal ID if successful, None if failed
        """
        company_name = company_data.get("company_name", "Unknown")

        try:
            clean_name = self._sanitize_company_name(company_name)

            deal_payload = {
                "name": clean_name,
                "attributes": {
                    "pipeline": pipeline_id,
                    "deal_stage": stage_id,
                    "funnel_status": status,
                },
            }

            if company_data.get("siren"):
                deal_payload["attributes"]["siren"] = company_data["siren"]

            if company_data.get("siret"):
                deal_payload["attributes"]["siret"] = company_data["siret"]

            if company_data.get("phone_number"):
                deal_payload["attributes"]["phone_number"] = company_data[
                    "phone_number"
                ]

            if company_data.get("nb_employees") is not None:
                deal_payload["attributes"]["nb_employees"] = company_data[
                    "nb_employees"
                ]

            if company_data.get("stage_since_days") is not None:
                deal_payload["attributes"]["stage_since_days"] = company_data[
                    "stage_since_days"
                ]

            if company_data.get("company_creation_date"):
                try:
                    deal_payload["attributes"][
                        "company_creation_date"
                    ] = company_data["company_creation_date"].isoformat()
                except (AttributeError, ValueError):
                    pass

            if "invited_employees_count" in company_data:
                deal_payload["attributes"][
                    "invited_employees_count"
                ] = company_data["invited_employees_count"]

            if "invitation_percentage" in company_data:
                deal_payload["attributes"][
                    "invitation_percentage"
                ] = company_data["invitation_percentage"]

            if "total_employees_count" in company_data:
                deal_payload["attributes"][
                    "total_employees_count"
                ] = company_data["total_employees_count"]

            if "validated_missions_count" in company_data:
                deal_payload["attributes"][
                    "validated_missions_count"
                ] = company_data["validated_missions_count"]

            url = f"{self.BASE_URL}/crm/deals"
            response = self._session.post(url, json=deal_payload)
            response.raise_for_status()

            deal_data = response.json()
            deal_id = deal_data.get("id")

            return deal_id

        except Exception as e:
            app.logger.error(
                f"Failed to create deal for company ID {company_data.get('company_id')}: {e}"
            )
            raise

    @check_api_key
    def get_existing_deals_by_pipeline(self, pipeline_id: str) -> list:
        try:
            deals_data = self.get_all_deals_by_pipeline(
                GetAllDealsByPipelineData(pipeline_id=pipeline_id)
            )

            deals = []
            for deal in deals_data.get("items", []):
                deal_name = self._extract_deal_name(deal)
                deal_attrs = deal.get("attributes", {})

                if deal_name:
                    deals.append(
                        {
                            "id": deal["id"],
                            "name": deal_name,
                            "stage_id": deal_attrs.get("deal_stage"),
                            "siren": deal_attrs.get("siren"),
                            "siret": deal_attrs.get("siret"),
                        }
                    )

            return deals

        except BrevoRequestError as e:
            app.logger.error(f"Failed to get existing deals: {e}")
            return []

    def _extract_deal_name(self, deal: dict) -> str:
        return deal["attributes"].get("deal_name", "Unknown")

    def _sanitize_company_name(self, name: str) -> str:
        if not name:
            return "Unknown Company"

        clean_name = name.strip()

        problematic_chars = ['"', "'", "\n", "\r", "\t"]
        for char in problematic_chars:
            clean_name = clean_name.replace(char, " ")

        clean_name = " ".join(clean_name.split())

        if len(clean_name) < 1:
            return "Unknown Company"

        if len(clean_name) > 100:
            clean_name = clean_name[:97] + "..."

        return clean_name

    @check_api_key
    def get_pipeline_id_by_name(self, pipeline_name: str) -> Optional[str]:
        try:
            pipelines = self.get_all_pipelines()
            for pipeline in pipelines:
                if pipeline["pipeline_name"] == pipeline_name:
                    return pipeline["pipeline"]
            return
        except BrevoRequestError as e:
            app.logger.error(f"Failed to get pipelines: {e}")
            raise

    @check_api_key
    def get_stage_mapping(self, pipeline_id: str) -> dict:
        try:
            pipeline_details = self.get_pipeline_details(pipeline_id)

            if isinstance(pipeline_details, list):
                pipeline_details = next(
                    (
                        p
                        for p in pipeline_details
                        if p["pipeline"] == pipeline_id
                    ),
                    None,
                )

            if not pipeline_details:
                return {}

            stage_mapping = {
                self._normalize_status(stage["name"]): stage["id"]
                for stage in pipeline_details.get("stages", [])
            }

            return stage_mapping

        except BrevoRequestError as e:
            app.logger.error(f"Failed to get pipeline details: {e}")
            return {}

    def _get_all_companies(self):
        if self._companies_cache is not None:
            return self._companies_cache

        all_companies = []
        page = 1
        limit = 1000
        max_companies = 5000

        while len(all_companies) < max_companies:
            url = f"{self.BASE_URL}/companies"
            params = {"limit": limit, "page": page}
            response = self._session.get(url, params=params)
            response.raise_for_status()

            response_data = response.json()
            companies_batch = response_data.get("items", [])

            if not companies_batch:
                break

            all_companies.extend(companies_batch)
            page += 1

            if len(companies_batch) < limit:
                break

        app.logger.debug(
            f"Retrieved {len(all_companies)} companies from Brevo API"
        )
        self._companies_cache = all_companies
        return all_companies

    @check_api_key
    def search_companies_by_identifier(
        self, siret: str = None, siren: str = None
    ) -> list:
        try:
            companies = self._get_all_companies()

            if siret:
                for company in companies:
                    attrs = company.get("attributes", {})
                    if attrs.get("siret") == siret:
                        return [company]

            if siren:
                for company in companies:
                    attrs = company.get("attributes", {})
                    company_siren = attrs.get("siren")
                    if str(company_siren) == str(siren):
                        app.logger.debug(
                            f"Found matching company with SIREN {siren}"
                        )
                        return [company]

            return []

        except Exception as e:
            app.logger.error(f"Failed to search companies: {e}")
            return []

    @check_api_key
    def get_unlinked_deals_by_pipeline(self, pipeline_id: str) -> list:
        try:
            deals_data = self.get_all_deals_by_pipeline(
                GetAllDealsByPipelineData(pipeline_id=pipeline_id)
            )

            unlinked_deals = []
            for deal in deals_data.get("items", []):
                if not deal.get("linkedCompaniesIds"):
                    deal_attrs = deal.get("attributes", {})
                    if deal_attrs.get("siren") or deal_attrs.get("siret"):
                        unlinked_deals.append(
                            {
                                "id": deal["id"],
                                "siren": deal_attrs.get("siren"),
                                "siret": deal_attrs.get("siret"),
                            }
                        )

            app.logger.info(
                f"Found {len(unlinked_deals)} unlinked deals with SIREN/SIRET"
            )
            return unlinked_deals

        except Exception as e:
            app.logger.error(f"Failed to get unlinked deals: {e}")
            return []

    @check_api_key
    def link_deal_to_company(self, deal_id: str, company_id: str) -> bool:
        try:
            url = f"{self.BASE_URL}/crm/deals/link-unlink/{deal_id}"
            payload = {"linkCompanyIds": [company_id]}
            response = self._session.patch(url, json=payload)
            response.raise_for_status()
            return True

        except Exception as e:
            app.logger.error(
                f"Failed to link deal {deal_id} to company {company_id}: {e}"
            )
            return False

    @check_api_key
    def get_companies_count(self) -> int:
        try:
            url = f"{self.BASE_URL}/companies"
            params = {"limit": 1, "page": 1}
            response = self._session.get(url, params=params)
            response.raise_for_status()

            response_data = response.json()

            total_count = (
                response_data.get("pager", {}).get("total", 0)
                or response_data.get("count", 0)
                or response_data.get("total", 0)
                or response_data.get("totalItems", 0)
                or response_data.get("totalCount", 0)
                or response_data.get("pager", {}).get("totalItems", 0)
                or response_data.get("pagination", {}).get("total", 0)
                or response_data.get("meta", {}).get("total", 0)
                or len(response_data.get("items", []))
            )

            app.logger.info(f"Total companies in Brevo: {total_count}")
            return total_count

        except Exception as e:
            app.logger.error(f"Failed to get companies count: {e}")
            app.logger.error(
                f"Response status: {getattr(response, 'status_code', 'unknown')}"
            )
            app.logger.error(
                f"Response text: {getattr(response, 'text', 'unknown')}"
            )
            return 0

    @check_api_key
    def link_unlinked_deals_paginated(
        self, pipeline_id: str, companies_per_page: int = 1000
    ) -> dict:
        try:
            unlinked_deals = self.get_unlinked_deals_by_pipeline(pipeline_id)
            if not unlinked_deals:
                return {"linked": 0, "errors": 0, "processed_deals": 0}

            total_companies = self.get_companies_count()
            total_pages = (
                total_companies + companies_per_page - 1
            ) // companies_per_page

            app.logger.info(f"Processing {len(unlinked_deals)} unlinked deals")
            app.logger.info(
                f"Total companies: {total_companies}, Pages to process: {total_pages}"
            )

            linked_count = 0
            error_count = 0
            current_page = 1

            while current_page <= total_pages:
                url = f"{self.BASE_URL}/companies"
                params = {"limit": companies_per_page, "page": current_page}
                response = self._session.get(url, params=params)
                response.raise_for_status()

                response_data = response.json()
                companies_batch = response_data.get("items", [])

                if not companies_batch:
                    break

                app.logger.info(
                    f"Processing companies page {current_page} ({len(companies_batch)} companies)"
                )

                companies_by_siren = {}
                companies_by_siret = {}

                for company in companies_batch:
                    attrs = company.get("attributes", {})
                    app.logger.debug(
                        f"Company {company['id']}: SIREN={attrs.get('siren')}, SIRET={attrs.get('siret')}"
                    )
                    if attrs.get("siren"):
                        companies_by_siren[str(attrs["siren"])] = company["id"]
                    if attrs.get("siret"):
                        companies_by_siret[str(attrs["siret"])] = company["id"]

                app.logger.debug(
                    f"Available company SIRENs: {list(companies_by_siren.keys())}"
                )
                app.logger.debug(
                    f"Available company SIRETs: {list(companies_by_siret.keys())}"
                )

                # Debug: show first few deal identifiers
                for i, deal in enumerate(unlinked_deals[:5]):
                    app.logger.debug(
                        f"Deal {deal['id']}: SIREN={deal.get('siren')}, SIRET={deal.get('siret')}"
                    )

                deals_to_remove = []
                for i, deal in enumerate(unlinked_deals):
                    company_id = None

                    if (
                        deal["siret"]
                        and str(deal["siret"]) in companies_by_siret
                    ):
                        company_id = companies_by_siret[str(deal["siret"])]
                    elif (
                        deal["siren"]
                        and str(deal["siren"]) in companies_by_siren
                    ):
                        company_id = companies_by_siren[str(deal["siren"])]

                    if company_id:
                        if self.link_deal_to_company(deal["id"], company_id):
                            linked_count += 1
                            deals_to_remove.append(i)
                            app.logger.debug(
                                f"Linked deal {deal['id']} to company {company_id}"
                            )
                        else:
                            error_count += 1

                for i in reversed(deals_to_remove):
                    unlinked_deals.pop(i)

                if not unlinked_deals:
                    app.logger.info("All deals have been processed")
                    break

                current_page += 1

                if len(companies_batch) < companies_per_page:
                    break

            total_processed = linked_count + error_count
            app.logger.info(
                f"Linking completed: {linked_count} linked, {error_count} errors, {len(unlinked_deals)} remaining"
            )
            return {
                "linked": linked_count,
                "errors": error_count,
                "processed_deals": total_processed,
            }

        except Exception as e:
            app.logger.error(f"Failed to link deals: {e}")
            return {"linked": 0, "errors": 1, "processed_deals": 0}

    def _normalize_status(self, status: str) -> str:
        return status.strip().lower()

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
