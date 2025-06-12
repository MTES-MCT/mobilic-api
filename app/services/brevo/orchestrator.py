"""Brevo synchronization orchestrator."""

import logging
import time
from typing import List, Dict, Any
from dataclasses import dataclass, field

from app.helpers.brevo import (
    BrevoApiClient,
    UpdateDealStageData,
    BrevoRequestError,
)
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
        acquisition_pipeline: str = None,
        activation_pipeline: str = None,
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
        acquisition_pipeline: str = None,
        activation_pipeline: str = None,
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
                elif deal.get("siren"):
                    deals_by_identifier[f"siren_{deal['siren']}"] = deal
                else:
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
        """Find existing deal by SIRET, SIREN or company name."""
        company_name = company["company_name"]

        if company.get("siret"):
            deal_key = f"siret_{company['siret']}"
            existing_deal = deals_by_identifier.get(deal_key)
            if existing_deal:
                return existing_deal, deal_key

        if company.get("siren"):
            deal_key = f"siren_{company['siren']}"
            existing_deal = deals_by_identifier.get(deal_key)
            if existing_deal:
                return existing_deal, deal_key

        deal_key = f"name_{company_name}"
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
            deals_by_identifier[f"name_{company_name}"] = deal_info

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
        target_stage_id = stage_mapping.get(
            self._normalize_status(target_status)
        )

        if not target_stage_id:
            result.errors.append(
                f"Stage '{target_status}' not found in pipeline"
            )
            return result

        existing_deal, _ = self._find_existing_deal(
            company, deals_by_identifier
        )

        if existing_deal:
            if existing_deal["stage_id"] != target_stage_id:
                update_data = UpdateDealStageData(
                    deal_id=existing_deal["id"],
                    pipeline_id=pipeline_id,
                    stage_id=target_stage_id,
                )
                self.brevo.update_deal_stage(update_data)
                result.updated_deals += 1
        else:
            self.logger.debug(
                f"Creating new deal for company ID: {company.get('company_id')}"
            )
            deal_id = self.brevo.create_deal_with_attributes(
                company, pipeline_id, target_stage_id, target_status
            )
            if deal_id:
                self.logger.debug(
                    f"Deal created successfully with ID: {deal_id}"
                )
                result.created_deals += 1
                self._update_deal_identifier(
                    company, deal_id, target_stage_id, deals_by_identifier
                )
            else:
                self.logger.debug(
                    f"Failed to create deal for company ID: {company.get('company_id')}"
                )

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
        return status.strip().lower()


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
