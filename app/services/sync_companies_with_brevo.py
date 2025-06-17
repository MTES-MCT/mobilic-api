import logging
from app import db
from app.helpers.brevo import (
    BrevoApiClient,
    UpdateDealStageData,
    GetAllDealsByPipelineData,
    GetCompanyData,
)

logger = logging.getLogger(__name__)


def sync_companies_with_brevo(
    brevo: BrevoApiClient, pipeline_names: list, verbose=False
):
    if verbose:
        logger.setLevel(logging.DEBUG)

    for pipeline_name in pipeline_names:
        try:
            logger.debug(f"Syncing pipeline: {pipeline_name}")
            pipeline_id = get_pipeline_id_by_name(brevo, pipeline_name)
            logger.debug(f"Pipeline ID: {pipeline_id}")

            stage_mapping = create_stage_mapping(brevo, pipeline_id)
            logger.debug(f"Stage mapping: {stage_mapping}")

            db_companies = get_companies_from_db_via_function()
            logger.debug(f"Companies from DB: {db_companies}")

            brevo_companies = get_companies_from_brevo(brevo, pipeline_id)
            logger.debug(f"Companies from Brevo: {brevo_companies}")

            updates_needed = compare_companies(
                db_companies, brevo_companies, stage_mapping
            )
            logger.debug(f"Updates needed: {updates_needed}")

            update_companies_in_brevo(
                brevo, updates_needed, stage_mapping, pipeline_id
            )
            logger.debug(f"Update complete for pipeline: {pipeline_name}")

        except ValueError as e:
            logger.error(f"Error syncing pipeline '{pipeline_name}': {e}")


def get_pipeline_id_by_name(brevo: BrevoApiClient, pipeline_name: str):
    pipelines = brevo.get_all_pipelines()
    for pipeline in pipelines:
        if pipeline["pipeline_name"] == pipeline_name:
            return pipeline["pipeline"]
    raise ValueError(f"Pipeline '{pipeline_name}' not found.")


def create_stage_mapping(brevo: BrevoApiClient, pipeline_id: str):
    pipeline_details = brevo.get_pipeline_details(pipeline_id)

    if isinstance(pipeline_details, list):
        pipeline_details = next(
            (p for p in pipeline_details if p["pipeline"] == pipeline_id), None
        )

    if not pipeline_details:
        raise ValueError(f"Pipeline with ID {pipeline_id} not found.")

    stage_mapping = {
        normalize_status(stage["name"]): stage["id"]
        for stage in pipeline_details.get("stages", [])
    }
    return stage_mapping


def get_companies_from_db_via_function():
    result = db.session.execute(
        "SELECT * FROM get_companies_status()"
    ).fetchall()

    companies = [
        {
            "id": row[0],
            "name": row[1],
            "status": row[6],
        }
        for row in result
    ]
    return companies


def get_companies_from_brevo(brevo: BrevoApiClient, pipeline_id: str):
    deals_data = brevo.get_all_deals_by_pipeline(
        GetAllDealsByPipelineData(pipeline_id=pipeline_id)
    )

    companies_in_brevo = []
    for deal in deals_data.get("items", []):
        linked_company_name = None
        original_deal_name = deal["attributes"].get("deal_name")
        if deal.get("linkedCompaniesIds"):
            company_id = deal["linkedCompaniesIds"][0]
            company_details = brevo.get_company(
                GetCompanyData(company_id=company_id)
            )
            linked_company_name = company_details["attributes"].get("name")
            logger.debug(
                f"linked company name : {linked_company_name} for deal : {original_deal_name}"
            )

        deal_name = (
            linked_company_name if linked_company_name else original_deal_name
        )

        companies_in_brevo.append(
            {
                "id": deal["id"],
                "name": deal_name,
                "original_deal_name": original_deal_name,
                "status": brevo.get_stage_name(
                    pipeline_id, deal["attributes"].get("deal_stage")
                ),
            }
        )

    return companies_in_brevo


def normalize_status(status):
    return status.strip().lower()


def compare_companies(db_companies, brevo_companies, stage_mapping):
    updates_needed = []
    processed_deals = set()

    brevo_dict = build_brevo_dict(brevo_companies)

    for db_company in db_companies:
        updates = process_db_company(
            db_company, brevo_dict, stage_mapping, processed_deals
        )
        updates_needed.extend(updates)

    return updates_needed


def build_brevo_dict(brevo_companies):
    brevo_dict = {}
    for company in brevo_companies:
        for key in ["name", "original_deal_name"]:
            if key in company:
                normalized_name = normalize_status(company[key])
                if normalized_name not in brevo_dict:
                    brevo_dict[normalized_name] = []
                brevo_dict[normalized_name].append(company)
    return brevo_dict


def process_db_company(db_company, brevo_dict, stage_mapping, processed_deals):
    updates = []
    db_company_name = normalize_status(db_company["name"])
    if db_company_name not in brevo_dict:
        logger.debug(f"Company not found in Brevo for: {db_company}")
        return updates

    for brevo_company in brevo_dict[db_company_name]:
        update = check_and_create_update(
            db_company, brevo_company, stage_mapping, processed_deals
        )
        if update:
            updates.append(update)

    return updates


def check_and_create_update(
    db_company, brevo_company, stage_mapping, processed_deals
):
    brevo_deal_id = brevo_company["id"]
    if brevo_deal_id in processed_deals:
        return None

    db_status_id, brevo_status_id = get_status_ids(
        db_company, brevo_company, stage_mapping
    )
    if db_status_id and db_status_id != brevo_status_id:
        processed_deals.add(brevo_deal_id)
        return {
            "db_company_id": db_company["id"],
            "brevo_deal_id": brevo_deal_id,
            "new_status": db_company["status"],
            "name": db_company["name"],
        }
    return None


def get_status_ids(db_company, brevo_company, stage_mapping):
    db_status = normalize_status(db_company.get("status", ""))
    brevo_status = normalize_status(brevo_company.get("status", ""))
    return stage_mapping.get(db_status), stage_mapping.get(brevo_status)


def update_companies_in_brevo(
    brevo: BrevoApiClient, updates_needed, stage_mapping, pipeline_id: str
):
    for update in updates_needed:
        stage_id = stage_mapping.get(update["new_status"].lower())
        if stage_id:
            update_data = UpdateDealStageData(
                deal_id=update["brevo_deal_id"],
                pipeline_id=pipeline_id,
                stage_id=stage_id,
            )
            try:
                brevo.update_deal_stage(update_data)
                company_name = update.get("name", "Unknown Company")
                print(
                    f"Updated deal '{company_name}' (ID: {update['brevo_deal_id']}) "
                    f"to stage '{update['new_status']}' in Brevo."
                )
            except Exception as e:
                print(
                    f"Failed to update deal {update['brevo_deal_id']} to stage '{update['new_status']}' in Brevo. Error: {e}"
                )
        else:
            print(
                f"Stage ID for status '{update['new_status']}' not found. Skipping update for deal {update['brevo_deal_id']}."
            )
