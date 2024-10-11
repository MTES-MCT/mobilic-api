import sys
from app.helpers.brevo import (
    BrevoApiClient,
    UpdateDealStageData,
    GetDealsByPipelineData,
)
from app import app
from config import BREVO_API_KEY_ENV


def get_pipeline_id_by_name(brevo: BrevoApiClient, pipeline_name: str) -> str:
    """
    Récupère l'ID d'une pipeline à partir de son nom.
    """
    pipelines = brevo.get_all_pipelines()
    for pipeline in pipelines:
        if pipeline["pipeline_name"] == pipeline_name:
            return pipeline["pipeline"]
    raise ValueError(f"Pipeline '{pipeline_name}' not found.")


def create_stage_mapping(brevo: BrevoApiClient, pipeline_id: str) -> dict:
    """
    Crée un mapping entre les noms de stages et les IDs de stages pour une pipeline donnée.
    """
    pipeline_details = brevo.get_pipeline_details(pipeline_id)
    stage_mapping = {
        stage["name"]: stage["id"]
        for stage in pipeline_details.get("stages", [])
    }
    return stage_mapping


def get_companies_from_db(session: Session):
    """
    Récupère les entreprises de la base de données et leur statut.
    """
    return session.query(Company.id, Company.name, Company.status).all()


def get_companies_from_brevo(brevo: BrevoApiClient, pipeline_id: str):
    """
    Récupère les deals (entreprises) de Brevo à partir de l'ID de la pipeline.
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
    Compare les entreprises en base avec celles de Brevo.
    Retourne une liste d'entreprises dont le statut doit être mis à jour.
    """
    updates_needed = []
    brevo_dict = {company["name"]: company for company in brevo_companies}

    for db_company in db_companies:
        brevo_company = brevo_dict.get(db_company.name)
        if brevo_company:
            db_status_id = stage_mapping.get(db_company.status)
            brevo_status_id = brevo_company["status"]
            if db_status_id and db_status_id != brevo_status_id:
                updates_needed.append(
                    {
                        "db_company_id": db_company.id,
                        "brevo_deal_id": brevo_company["id"],
                        "new_status": db_company.status,
                    }
                )
    return updates_needed


def update_companies_in_brevo(
    brevo: BrevoApiClient, updates_needed, stage_mapping, pipeline_id: str
):
    """
    Met à jour les statuts des entreprises dans Brevo.
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


def sync_companies_with_brevo(
    session: Session, brevo: BrevoApiClient, pipeline_names: list
):
    """
    Lance la synchronisation des entreprises entre la base de données et Brevo pour chaque pipeline spécifiée.
    """
    for pipeline_name in pipeline_names:
        try:
            # Récupérer l'ID de la pipeline à partir de son nom
            pipeline_id = get_pipeline_id_by_name(brevo, pipeline_name)

            # Créer un mapping entre les stages et les statuts en base de données
            stage_mapping = create_stage_mapping(brevo, pipeline_id)

            # Récupérer les entreprises de la base de données
            db_companies = get_companies_from_db(session)

            # Récupérer les entreprises de Brevo
            brevo_companies = get_companies_from_brevo(brevo, pipeline_id)

            # Comparer les données et identifier les mises à jour nécessaires
            updates_needed = compare_companies(
                db_companies, brevo_companies, stage_mapping
            )

            # Mettre à jour les statuts dans Brevo
            update_companies_in_brevo(
                brevo, updates_needed, stage_mapping, pipeline_id
            )

        except ValueError as e:
            print(f"Error syncing pipeline '{pipeline_name}': {e}")


if __name__ == "__main__":
    # Initialisation de l'API Brevo
    brevo = BrevoApiClient(app.config[BREVO_API_KEY_ENV])

    # Pipeline names could be passed as command-line arguments or retrieved from a config file
    # Accept pipeline names as command-line arguments
    pipeline_names = sys.argv[1:]

    if not pipeline_names:
        print("Please provide at least one pipeline name.")
        sys.exit(1)

    # Démarrer une session SQLAlchemy (à adapter selon votre configuration)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        sync_companies_with_brevo(session, brevo, pipeline_names)
    finally:
        session.close()
