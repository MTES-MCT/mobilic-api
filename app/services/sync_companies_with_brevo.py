import logging
from app import db
from app.helpers.brevo import (
    BrevoApiClient,
    UpdateDealStageData,
    GetDealsByPipelineData,
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


def create_stage_mapping(brevo: BrevoApiClient, pipeline_id: str) -> dict:
    pipeline_details = brevo.get_pipeline_details(pipeline_id)

    if isinstance(pipeline_details, list):
        pipeline_details = next(
            (p for p in pipeline_details if p["pipeline"] == pipeline_id), None
        )

    if not pipeline_details:
        raise ValueError(f"Pipeline with ID {pipeline_id} not found.")

    stage_mapping = {
        stage["name"]: stage["id"]
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
    """
    Retrieve deals (companies) from Brevo using the pipeline ID.
    """
    deals_data = brevo.get_deals_by_pipeline(
        GetDealsByPipelineData(pipeline_id=pipeline_id, limit=100)
    )
    companies_in_brevo = [
        {
            "id": deal["id"],
            "name": deal["attributes"].get("deal_name"),
            "status": brevo.get_stage_name(
                pipeline_id, deal["attributes"].get("deal_stage")
            ),
        }
        for deal in deals_data.get("items", [])
    ]
    return companies_in_brevo


def normalize_status(status):
    return status.strip().lower()


def compare_companies(db_companies, brevo_companies, stage_mapping):
    updates_needed = []
    brevo_dict = {company["name"]: company for company in brevo_companies}

    for db_company in db_companies:
        brevo_company = brevo_dict.get(db_company["name"])
        db_status = normalize_status(db_company["status"])
        brevo_status = normalize_status(brevo_company["status"])
        db_status_id = stage_mapping.get(db_status)
        brevo_status_id = stage_mapping.get(brevo_status)
        if db_status_id and db_status_id != brevo_status_id:
            updates_needed.append(
                {
                    "db_company_id": db_company["id"],
                    "brevo_deal_id": brevo_company["id"],
                    "new_status": db_company["status"],
                    "name": db_company["name"],
                }
            )
    return updates_needed


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
