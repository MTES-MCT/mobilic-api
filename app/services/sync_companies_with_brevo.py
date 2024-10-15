from app import db
from app.helpers.brevo import (
    BrevoApiClient,
    UpdateDealStageData,
    GetDealsByPipelineData,
)


def sync_companies_with_brevo(brevo: BrevoApiClient, pipeline_names: list):
    """
    Launches the synchronization of companies between the database and Brevo for each specified pipeline.
    """
    for pipeline_name in pipeline_names:
        try:
            # Retrieve the pipeline ID from its name
            pipeline_id = get_pipeline_id_by_name(brevo, pipeline_name)

            # Create a mapping between stages and statuses in the database
            stage_mapping = create_stage_mapping(brevo, pipeline_id)

            # Retrieve companies from the database using the stored function get_companies_status()
            db_companies = get_companies_from_db_via_function()

            # Retrieve companies from Brevo
            brevo_companies = get_companies_from_brevo(brevo, pipeline_id)

            # Compare the data and identify necessary updates
            updates_needed = compare_companies(
                db_companies, brevo_companies, stage_mapping
            )

            # Update statuses in Brevo
            update_companies_in_brevo(
                brevo, updates_needed, stage_mapping, pipeline_id
            )

        except ValueError as e:
            print(f"Error syncing pipeline '{pipeline_name}': {e}")


def get_pipeline_id_by_name(brevo: BrevoApiClient, pipeline_name: str):
    """
    Retrieve the ID of a pipeline by its name.
    """
    pipelines = brevo.get_all_pipelines()
    for pipeline in pipelines:
        if pipeline["pipeline_name"] == pipeline_name:
            return pipeline["pipeline"]
    raise ValueError(f"Pipeline '{pipeline_name}' not found.")


def create_stage_mapping(brevo: BrevoApiClient, pipeline_id: str):
    """
    Create a mapping between stage names and stage IDs for a given pipeline.
    """
    pipeline_details = brevo.get_pipeline_details(pipeline_id)
    stage_mapping = {
        stage["name"]: stage["id"]
        for stage in pipeline_details.get("stages", [])
    }
    return stage_mapping


def get_companies_from_db_via_function():
    """
    Call the stored function 'get_companies_status' from the database.
    """
    result = db.session.execute(
        "SELECT * FROM get_companies_status()"
    ).fetchall()

    # Transform the result into a list of dictionaries
    companies = [
        {
            "id": row[0],
            "name": row[1],
            "status": row[2],
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


def compare_companies(db_companies, brevo_companies, stage_mapping):
    """
    Compare the companies in the database with those in Brevo.
    Returns a list of companies whose statuses need to be updated.
    """
    updates_needed = []
    brevo_dict = {company["name"]: company for company in brevo_companies}

    for db_company in db_companies:
        brevo_company = brevo_dict.get(db_company["name"])
        if brevo_company:
            db_status_id = stage_mapping.get(db_company["status"])
            brevo_status_id = brevo_company["status"]
            if db_status_id and db_status_id != brevo_status_id:
                updates_needed.append(
                    {
                        "db_company_id": db_company["id"],
                        "brevo_deal_id": brevo_company["id"],
                        "new_status": db_company["status"],
                    }
                )
    return updates_needed


def update_companies_in_brevo(
    brevo: BrevoApiClient, updates_needed, stage_mapping, pipeline_id: str
):
    """
    Update the statuses of companies in Brevo.
    """
    for update in updates_needed:
        stage_id = stage_mapping.get(update["new_status"])
        if stage_id:
            update_data = UpdateDealStageData(
                deal_id=update["brevo_deal_id"],
                pipeline_id=pipeline_id,
                stage_id=stage_id,
            )
            brevo.update_deal_stage(update_data)
            print(
                f"Updated deal {update['brevo_deal_id']} to stage '{update['new_status']}' in Brevo."
            )
