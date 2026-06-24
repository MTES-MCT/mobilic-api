"""Brevo synchronization orchestrator."""

import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.helpers.brevo import BrevoApiClient, BrevoRequestError
from .acquisition_data_finder import AcquisitionDataFinder
from .activation_data_finder import ActivationDataFinder


logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a Brevo synchronization operation."""

    total_companies: int = 0
    created_deals: int = 0
    updated_deals: int = 0
    errors: List[str] = field(default_factory=list)
    acquisition_synced: int = 0
    activation_synced: int = 0


class BrevoSyncOrchestrator:
    """Orchestrator for synchronizing company data with Brevo pipelines."""

    def __init__(self, brevo_client: BrevoApiClient):
        self.brevo = brevo_client
        self.logger = logging.getLogger(self.__class__.__name__)

        self.acquisition_finder = AcquisitionDataFinder()
        self.activation_finder = ActivationDataFinder()

        self.MAX_REQUESTS_PER_BATCH = 50
        self.DELAY_BETWEEN_BATCHES = 2
        self.DEFAULT_ACQUISITION_PIPELINE = "Acquisition"
        self.DEFAULT_ACTIVATION_PIPELINE = "Activation"

    def sync_all_funnels(
        self,
        acquisition_pipeline: Optional[str] = None,
        activation_pipeline: Optional[str] = None,
        dry_run: bool = False,
    ) -> SyncResult:
        """Synchronize both acquisition and activation funnels.

        Args:
            acquisition_pipeline: Brevo pipeline name for acquisition
            activation_pipeline: Brevo pipeline name for activation
            dry_run: If True, simulate sync without making actual changes

        Returns:
            SyncResult object containing sync statistics and any errors
        """

        activation_data = self.activation_finder.find_companies()
        activation_company_ids = [c["company_id"] for c in activation_data]

        acquisition_data = self.acquisition_finder.find_companies(
            exclude_company_ids=activation_company_ids
        )

        return self.sync_dual_pipeline_funnel(
            acquisition_data=acquisition_data,
            activation_data=activation_data,
            acquisition_pipeline=acquisition_pipeline,
            activation_pipeline=activation_pipeline,
            dry_run=dry_run,
        )

    def sync_dual_pipeline_funnel(
        self,
        acquisition_data: List[Dict[str, Any]],
        activation_data: List[Dict[str, Any]],
        acquisition_pipeline: Optional[str] = None,
        activation_pipeline: Optional[str] = None,
        dry_run: bool = False,
    ) -> SyncResult:
        """Synchronize companies to separate acquisition and activation pipelines.

        Args:
            acquisition_data: Companies data for acquisition pipeline
            activation_data: Companies data for activation pipeline
            acquisition_pipeline: Brevo pipeline name for acquisition
            activation_pipeline: Brevo pipeline name for activation
            dry_run: If True, simulate sync without making actual changes

        Returns:
            SyncResult object containing sync statistics and any errors
        """
        acquisition_pipeline = (
            acquisition_pipeline or self.DEFAULT_ACQUISITION_PIPELINE
        )
        activation_pipeline = (
            activation_pipeline or self.DEFAULT_ACTIVATION_PIPELINE
        )

        self.logger.info(
            f"Starting dual pipeline sync: {len(acquisition_data)} acquisition + {len(activation_data)} activation"
        )

        result = SyncResult(
            total_companies=len(acquisition_data) + len(activation_data)
        )

        try:
            if acquisition_data:
                acq_result = self._sync_pipeline(
                    acquisition_data,
                    acquisition_pipeline,
                    "acquisition_status",
                    dry_run,
                )
                result.acquisition_synced = (
                    acq_result.created_deals + acq_result.updated_deals
                )
                result.created_deals += acq_result.created_deals
                result.updated_deals += acq_result.updated_deals
                result.errors.extend(acq_result.errors)

            if activation_data:
                act_result = self._sync_pipeline(
                    activation_data,
                    activation_pipeline,
                    "activation_status",
                    dry_run,
                )
                result.activation_synced = (
                    act_result.created_deals + act_result.updated_deals
                )
                result.created_deals += act_result.created_deals
                result.updated_deals += act_result.updated_deals
                result.errors.extend(act_result.errors)

            self.logger.info(
                f"Sync completed: {result.created_deals} created, {result.updated_deals} updated"
            )
            return result

        except Exception as e:
            error_msg = f"Dual sync failed: {str(e)}"
            self.logger.error(error_msg)
            result.errors.append(error_msg)
            return result

    def _sync_pipeline(
        self,
        companies_data: List[Dict[str, Any]],
        pipeline_name: str,
        status_field: str,
        dry_run: bool = False,
    ) -> SyncResult:
        result = SyncResult(total_companies=len(companies_data))

        try:
            pipeline_id = self.brevo.get_pipeline_id_by_name(pipeline_name)
            if not pipeline_id:
                error_msg = f"Pipeline '{pipeline_name}' not found"
                result.errors.append(error_msg)
                return result

            stage_mapping = self.brevo.get_stage_mapping(pipeline_id)
            if not stage_mapping:
                error_msg = f"No stages found for pipeline '{pipeline_name}'"
                result.errors.append(error_msg)
                return result

            if dry_run:
                return self._simulate_sync(
                    companies_data, stage_mapping, result, status_field
                )

            existing_deals = self.brevo.get_existing_deals_by_pipeline(
                pipeline_id
            )
            deals_by_identifier = {}
            for deal in existing_deals:
                if deal.get("siret"):
                    deals_by_identifier[f"siret_{deal['siret']}"] = deal
                if deal.get("siren"):
                    deals_by_identifier[f"siren_{deal['siren']}"] = deal
                if not deal.get("siret") and not deal.get("siren"):
                    deals_by_identifier[f"name_{deal['name']}"] = deal

            batch_size = self.MAX_REQUESTS_PER_BATCH
            for i in range(0, len(companies_data), batch_size):
                batch = companies_data[i : i + batch_size]

                batch_result = self._sync_company_batch(
                    batch,
                    pipeline_id,
                    stage_mapping,
                    deals_by_identifier,
                    status_field,
                )

                result.created_deals += batch_result.created_deals
                result.updated_deals += batch_result.updated_deals
                result.errors.extend(batch_result.errors)

                # Rate limiting
                if i + batch_size < len(companies_data):
                    time.sleep(self.DELAY_BETWEEN_BATCHES)

            return result

        except Exception as e:
            error_msg = f"Pipeline sync failed: {str(e)}"
            self.logger.error(error_msg)
            result.errors.append(error_msg)
            raise

    def _sync_company_batch(
        self,
        batch: List[Dict[str, Any]],
        pipeline_id: str,
        stage_mapping: Dict[str, str],
        deals_by_identifier: Dict[str, Dict[str, Any]],
        status_field: str,
    ) -> SyncResult:
        result = SyncResult()

        for company in batch:
            try:
                company_result = self._sync_single_company(
                    company,
                    pipeline_id,
                    stage_mapping,
                    deals_by_identifier,
                    status_field,
                )
                result.created_deals += company_result.created_deals
                result.updated_deals += company_result.updated_deals
                result.errors.extend(company_result.errors)

            except Exception as e:
                error_msg = f"Failed to process company {company.get('company_name', 'Unknown')}: {str(e)}"
                self.logger.error(error_msg)
                result.errors.append(error_msg)

        return result

    def _find_existing_deal(
        self,
        company: Dict[str, Any],
        deals_by_identifier: Dict[str, Dict[str, Any]],
    ) -> tuple:
        """Find existing deal by SIREN, SIRET or company name."""
        company_name = company["company_name"]

        if company.get("siren"):
            deal_key = f"siren_{company['siren']}"
            existing_deal = deals_by_identifier.get(deal_key)
            if existing_deal:
                return existing_deal, deal_key

        if company.get("siret"):
            deal_key = f"siret_{company['siret']}"
            existing_deal = deals_by_identifier.get(deal_key)
            if existing_deal:
                return existing_deal, deal_key

        sanitized_name = self.brevo.sanitize_company_name(company_name)
        deal_key = f"name_{sanitized_name}"
        existing_deal = deals_by_identifier.get(deal_key)
        return existing_deal, deal_key

    def _update_deal_identifier(
        self,
        company: Dict[str, Any],
        deal_id: str,
        target_stage_id: str,
        deals_by_identifier: Dict[str, Dict[str, Any]],
    ):
        """Update deals_by_identifier with new deal info."""
        deal_info = {"id": deal_id, "stage_id": target_stage_id}
        company_name = company["company_name"]

        if company.get("siret"):
            deals_by_identifier[f"siret_{company['siret']}"] = deal_info
        elif company.get("siren"):
            deals_by_identifier[f"siren_{company['siren']}"] = deal_info
        else:
            sanitized_name = self.brevo.sanitize_company_name(company_name)
            deals_by_identifier[f"name_{sanitized_name}"] = deal_info

    def _link_deal_to_company(
        self,
        company: Dict[str, Any],
        deal_id: str,
        existing_deal: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Link deal to Brevo company entity."""
        api_calls = 0
        try:
            # Search for company by SIRET first, then SIREN
            companies = self.brevo.search_companies_by_identifier(
                siret=company.get("siret"), siren=company.get("siren")
            )

            if not companies:
                self.logger.warning(
                    f"No Brevo company found for {company.get('company_name')} "
                    f"(SIREN: {company.get('siren')}, SIRET: {company.get('siret')})"
                )
                return api_calls

            brevo_company = companies[0]
            company_id = brevo_company.get("id")

            if not company_id:
                self.logger.error(f"Company found but no ID: {brevo_company}")
                return api_calls

            # Check if company_id attribute needs updating
            current_company_id = (
                existing_deal.get("company_id") if existing_deal else None
            )
            if current_company_id != str(company_id):
                try:
                    self.brevo.update_deal(
                        deal_id=deal_id,
                        attributes={"company_id": str(company_id)},
                    )
                    api_calls += 1
                    self.logger.debug(
                        f"Set company_id attribute on deal {deal_id}"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to set company_id attribute on deal {deal_id}: {e}"
                    )
            else:
                self.logger.debug(
                    f"Deal {deal_id} already has company_id={company_id}, skipping update"
                )

            # Check if deal-company link already exists
            existing_links = (
                existing_deal.get("linkedCompaniesIds", [])
                if existing_deal
                else []
            )
            if company_id not in existing_links:
                link_success = self.brevo.link_deal_to_company(
                    deal_id, company_id
                )
                api_calls += 1
                if not link_success:
                    self.logger.error(
                        f"Failed to link deal {deal_id} to company {company_id} "
                        f"({company.get('company_name')})"
                    )
                    return api_calls
                self.logger.debug(
                    f"Linked deal {deal_id} to company {company_id} "
                    f"({company.get('company_name')})"
                )
            else:
                self.logger.debug(
                    f"Deal {deal_id} already linked to company {company_id}, skipping"
                )

            return api_calls

        except Exception as e:
            self.logger.error(f"Error linking deal {deal_id} to company: {e}")
            return api_calls

    def _link_manager_contact_to_deal(
        self,
        company: Dict[str, Any],
        deal_id: str,
        existing_deal: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Link manager contact to deal. Raises BrevoRequestError on API errors."""
        api_calls = 0
        admin_email = company.get("admin_email")
        if not admin_email:
            self.logger.debug(
                f"No admin email for company {company.get('company_name')}"
            )
            return api_calls

        # get_contact_by_email returns None for 404, raises BrevoRequestError for API errors
        contact = self.brevo.get_contact_by_email(admin_email)
        api_calls += 1

        if not contact:
            self.logger.debug(
                f"Contact not found for email {admin_email} "
                f"({company.get('company_name')})"
            )
            return api_calls

        contact_id = contact.get("id")
        if not contact_id:
            self.logger.error(f"Contact found but no ID: {contact}")
            return api_calls

        # Check if contact is already linked to deal
        existing_contacts = (
            existing_deal.get("linkedContactsIds", []) if existing_deal else []
        )
        if contact_id not in existing_contacts:
            success = self.brevo.link_contact_to_deal(deal_id, contact_id)
            api_calls += 1

            if success:
                self.logger.debug(
                    f"Linked contact {contact_id} ({admin_email}) to deal {deal_id}"
                )
            else:
                self.logger.error(
                    f"Failed to link contact {contact_id} to deal {deal_id}"
                )
        else:
            self.logger.debug(
                f"Contact {contact_id} already linked to deal {deal_id}, skipping"
            )

        return api_calls

    def _build_deal_attributes(
        self, company: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build attributes payload for deal update.

        Only includes fields that are present in company data.
        Absent keys are ignored, but explicit None values are preserved
        to allow clearing fields in Brevo.
        """
        field_mappings = {
            "siren": "siren",
            "siret": "siret",
            "phone_number": "phone_number",
            "nb_employees": "nb_employees",
            "stage_since_days": "stage_since_days",
            "total_employees_count": "total_employees_count",
            "invited_employees_count": "invited_employees_count",
            "invitation_percentage": "invitation_percentage",
            "validated_missions_count": "validated_missions_count",
            "active_employees_count": "active_employees_count",
        }

        return {
            brevo_key: company[company_key]
            for company_key, brevo_key in field_mappings.items()
            if company_key in company
        }

    def _sync_single_company(
        self,
        company: Dict[str, Any],
        pipeline_id: str,
        stage_mapping: Dict[str, str],
        deals_by_identifier: Dict[str, Dict[str, Any]],
        status_field: str,
    ) -> SyncResult:
        result = SyncResult()

        target_status = company.get(status_field, "Entreprise inscrite")
        normalized_status = self._normalize_status(target_status)
        target_stage_id = stage_mapping.get(normalized_status)

        if not target_stage_id:
            result.errors.append(
                f"Stage '{target_status}' not found in pipeline"
            )
            return result

        existing_deal, _ = self._find_existing_deal(
            company, deals_by_identifier
        )

        if existing_deal:
            attributes = self._build_deal_attributes(company)
            stage_changed = existing_deal["stage_id"] != target_stage_id
            changed_attributes = {
                key: value
                for key, value in attributes.items()
                if str(existing_deal.get(key)) != str(value)
            }

            if stage_changed or changed_attributes:
                self.brevo.update_deal(
                    deal_id=existing_deal["id"],
                    pipeline_id=pipeline_id if stage_changed else None,
                    stage_id=target_stage_id if stage_changed else None,
                    attributes=changed_attributes or None,
                )
                result.updated_deals += 1

            # Link deal to company and contact (skips if already linked)
            self._link_deal_to_company(
                company, existing_deal["id"], existing_deal
            )
            try:
                self._link_manager_contact_to_deal(
                    company, existing_deal["id"], existing_deal
                )
            except BrevoRequestError as e:
                self.logger.warning(f"Could not link contact: {e}")
        else:
            deal_id = self.brevo.create_deal_with_attributes(
                company, pipeline_id, target_stage_id, target_status
            )
            if deal_id:
                result.created_deals += 1
                self._update_deal_identifier(
                    company, deal_id, target_stage_id, deals_by_identifier
                )
                # Link newly created deal to company and contact
                self._link_deal_to_company(company, deal_id, None)
                try:
                    self._link_manager_contact_to_deal(company, deal_id, None)
                except BrevoRequestError as e:
                    self.logger.warning(f"Could not link contact: {e}")

        return result

    def _simulate_sync(
        self,
        companies_data: List[Dict[str, Any]],
        stage_mapping: Dict[str, str],
        result: SyncResult,
        status_field: str,
    ) -> SyncResult:
        status_counts = {}
        unmapped_statuses = set()

        for company in companies_data:
            target_status = company.get(status_field, "Entreprise inscrite")
            normalized_status = self._normalize_status(target_status)

            status_counts[target_status] = (
                status_counts.get(target_status, 0) + 1
            )

            if normalized_status not in stage_mapping:
                unmapped_statuses.add(target_status)

        self.logger.info("DRY RUN - Sync simulation results:")
        self.logger.info(f"Total companies: {len(companies_data)}")

        for status, count in sorted(
            status_counts.items(), key=lambda x: x[1], reverse=True
        ):
            mapped = (
                "✓" if self._normalize_status(status) in stage_mapping else "✗"
            )
            self.logger.info(f"  {mapped} {count:3d} companies: {status}")

        if unmapped_statuses:
            self.logger.warning(f"Unmapped statuses: {unmapped_statuses}")
            result.errors.extend(
                [f"Unmapped status: {status}" for status in unmapped_statuses]
            )

        result.created_deals = len(companies_data)
        return result

    def _normalize_status(self, status: str) -> str:
        normalized = status.strip().lower()
        # Replace typographic apostrophes with ASCII apostrophe
        normalized = normalized.replace("'", "'")  # U+2019 -> U+0027
        normalized = normalized.replace("'", "'")  # U+2018 -> U+0027
        return normalized

    def _build_siren_company_mapping(
        self, existing_deals: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Build SIREN -> Mobilic company_id mapping from existing deals."""
        from app.models import Company
        from app import db

        if not any(deal.get("siren") for deal in existing_deals):
            return {}

        siren_to_company_id = {}
        companies = (
            db.session.query(Company.id, Company.siren_api_info)
            .filter(Company.siren_api_info.isnot(None))
            .all()
        )

        for company in companies:
            if company.siren_api_info and company.siren_api_info.get(
                "uniteLegale"
            ):
                siren = company.siren_api_info["uniteLegale"].get("siren")
                if siren:
                    siren_to_company_id[siren] = company.id

        return siren_to_company_id

    def _prepare_deal_company_data(
        self,
        deal: Dict[str, Any],
        siren_to_company_id: Dict[str, int],
        admin_info_by_company_id: Dict[int, Dict],
    ) -> Dict[str, Any]:
        """Build company_data dict for a deal, including admin email if available."""
        company_data = {
            "company_name": deal.get("name", "Unknown"),
            "siren": deal.get("siren"),
            "siret": deal.get("siret"),
        }

        mobilic_company_id = siren_to_company_id.get(deal.get("siren") or "")
        if mobilic_company_id:
            admin_info = admin_info_by_company_id.get(mobilic_company_id, {})
            if admin_info.get("email"):
                company_data["admin_email"] = admin_info["email"]

        return company_data

    def _process_deal_linking_dry_run(
        self, deal_id: str, company_data: Dict[str, Any]
    ) -> tuple:
        """Simulate deal linking (dry-run). Returns (linked, error, api_calls)."""
        company_name = company_data.get("company_name")
        companies = self.brevo.search_companies_by_identifier(
            siret=company_data.get("siret"),
            siren=company_data.get("siren"),
        )
        if companies:
            self.logger.info(
                f"[DRY RUN] Would link deal {deal_id} to company "
                f"{companies[0].get('id')} ({company_name})"
                f"{' with contact' if company_data.get('admin_email') else ' (no contact)'}"
            )
            return 1, 0, 0

        self.logger.warning(
            f"[DRY RUN] No company found for deal {deal_id} ({company_name})"
        )
        return 0, 1, 0

    def _execute_deal_linking(
        self, deal_id: str, deal: Dict[str, Any], company_data: Dict[str, Any]
    ) -> tuple:
        """Execute actual deal linking. Returns (linked, error, api_calls)."""
        company_api_calls = self._link_deal_to_company(
            company_data, deal_id, deal
        )

        try:
            contact_api_calls = self._link_manager_contact_to_deal(
                company_data, deal_id, deal
            )
        except BrevoRequestError as e:
            self.logger.error(f"Failed to link contact: {e}")
            return 1 if company_api_calls > 0 else 0, 1, company_api_calls + 1

        total_api_calls = company_api_calls + contact_api_calls
        linked = 1 if company_api_calls > 0 else 0
        # Count as error only if company link failed, not when contact is simply absent
        has_error = company_api_calls == 0 and (
            company_data.get("admin_email") or contact_api_calls > 0
        )
        return linked, 1 if has_error else 0, total_api_calls

    def link_existing_deals_to_companies(
        self, pipeline_name: str, dry_run: bool = False
    ) -> Dict[str, int]:
        """Link existing deals to their corresponding Brevo companies and contacts.

        This is a migration function to link deals that were created before
        automatic company linking was implemented.

        Args:
            pipeline_name: Name of the Brevo pipeline to process
            dry_run: If True, only simulate linking without making changes

        Returns:
            Dictionary with statistics: linked_count, error_count, skipped_count
        """
        from .utils import get_admin_info

        self.logger.info(
            f"Starting deal-company linking for pipeline '{pipeline_name}' "
            f"(dry_run={dry_run})"
        )

        try:
            pipeline_id = self.brevo.get_pipeline_id_by_name(pipeline_name)
            if not pipeline_id:
                self.logger.error(f"Pipeline '{pipeline_name}' not found")
                return {
                    "linked_count": 0,
                    "error_count": 1,
                    "skipped_count": 0,
                }

            existing_deals = self.brevo.get_existing_deals_by_pipeline(
                pipeline_id
            )
            self.logger.info(f"Found {len(existing_deals)} deals in pipeline")

            siren_to_company_id = self._build_siren_company_mapping(
                existing_deals
            )
            admin_info_by_company_id = get_admin_info(
                list(set(siren_to_company_id.values()))
            )

            linked_count = 0
            error_count = 0
            skipped_count = 0
            api_calls_count = 0

            for deal in existing_deals:
                if not deal.get("siren") and not deal.get("siret"):
                    self.logger.debug(
                        f"Skipping deal {deal.get('id')} ({deal.get('name', 'Unknown')}): no SIREN/SIRET"
                    )
                    skipped_count += 1
                    continue

                company_data = self._prepare_deal_company_data(
                    deal, siren_to_company_id, admin_info_by_company_id
                )

                if dry_run:
                    linked, error, api_calls = (
                        self._process_deal_linking_dry_run(
                            deal.get("id"), company_data
                        )
                    )
                else:
                    linked, error, api_calls = self._execute_deal_linking(
                        deal.get("id"), deal, company_data
                    )

                linked_count += linked
                error_count += error
                api_calls_count += api_calls

                if (
                    api_calls_count > 0
                    and api_calls_count % (self.MAX_REQUESTS_PER_BATCH * 2)
                    == 0
                ):
                    self.logger.info(
                        f"Progress: {linked_count} linked, {error_count} errors, "
                        f"{skipped_count} skipped ({api_calls_count} API calls)"
                    )
                    time.sleep(self.DELAY_BETWEEN_BATCHES)

            self.logger.info(
                f"Linking completed: {linked_count} linked, {error_count} errors, "
                f"{skipped_count} skipped ({api_calls_count} total API calls)"
            )
            return {
                "linked_count": linked_count,
                "error_count": error_count,
                "skipped_count": skipped_count,
            }

        except Exception as e:
            self.logger.error(f"Failed to link deals: {str(e)}")
            return {"linked_count": 0, "error_count": 1, "skipped_count": 0}


def sync_all_funnels(
    brevo_client: BrevoApiClient,
    acquisition_pipeline: str = "Acquisition",
    activation_pipeline: str = "Activation",
    dry_run: bool = False,
) -> SyncResult:
    orchestrator = BrevoSyncOrchestrator(brevo_client)

    return orchestrator.sync_all_funnels(
        acquisition_pipeline=acquisition_pipeline,
        activation_pipeline=activation_pipeline,
        dry_run=dry_run,
    )


def sync_dual_pipeline_funnel(
    acquisition_data: List[Dict[str, Any]],
    activation_data: List[Dict[str, Any]],
    brevo_client: BrevoApiClient,
    acquisition_pipeline: str = "Acquisition",
    activation_pipeline: str = "Activation",
    dry_run: bool = False,
) -> SyncResult:
    orchestrator = BrevoSyncOrchestrator(brevo_client)

    return orchestrator.sync_dual_pipeline_funnel(
        acquisition_data=acquisition_data,
        activation_data=activation_data,
        acquisition_pipeline=acquisition_pipeline,
        activation_pipeline=activation_pipeline,
        dry_run=dry_run,
    )
