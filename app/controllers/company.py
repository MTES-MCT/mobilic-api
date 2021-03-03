import graphene
from flask import request, jsonify
from datetime import datetime, date
from graphene.types.generic import GenericScalar
import requests
from sqlalchemy.orm import selectinload

from app.controllers.utils import atomic_transaction
from app.data_access.company import CompanyOutput
from app.domain.permissions import (
    belongs_to_company_at,
    ConsultationScope,
)
from app.helpers.authentication import require_auth, AuthenticationError
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated,
    current_user,
)
from app import siren_api_client, mailer
from app.helpers.xls import send_work_days_as_excel
from app.models import Company, Employment
from app.models.employment import (
    EmploymentRequestValidationStatus,
    EmploymentOutput,
)
from app.models.queries import company_queries_with_all_relations
from app import db, app


class CompanySignUp(graphene.Mutation):
    """
    Inscription d'une nouvelle entreprise.

    Retourne l'entreprise nouvellement créée
    """

    class Arguments:
        usual_name = graphene.String(
            required=True, description="Nom usuel de l'entreprise"
        )
        siren = graphene.Int(
            required=True, description="Numéro SIREN de l'entreprise"
        )
        sirets = graphene.List(
            graphene.String,
            required=False,
            description="Liste des SIRET des établissements associés à l'entreprise",
        )

    company = graphene.Field(CompanyOutput)
    employment = graphene.Field(EmploymentOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, usual_name, siren, sirets):
        with atomic_transaction(commit_at_end=True):
            now = datetime.now()
            company = Company(
                usual_name=usual_name, siren=siren, sirets=sirets
            )
            db.session.add(company)
            db.session.flush()  # Early check for SIREN duplication

            try:
                company.siren_api_info = siren_api_client.get_siren_info(siren)
            except Exception as e:
                app.logger.warning(
                    f"Could not add SIREN API info for company of SIREN {siren} : {e}"
                )

            admin_employment = Employment(
                is_primary=False if current_user.primary_company else True,
                user_id=current_user.id,
                company=company,
                start_date=now.date(),
                validation_time=now,
                validation_status=EmploymentRequestValidationStatus.APPROVED,
                has_admin_rights=True,
                reception_time=now,
                submitter_id=current_user.id,
            )
            db.session.add(admin_employment)

        app.logger.info(
            f"Signed up new company {company}",
            extra={"post_to_slack": True, "emoji": ":tada:"},
        )

        try:
            mailer.send_company_creation_email(company, current_user)
        except Exception as e:
            app.logger.exception(e)

        if app.config["INTEGROMAT_COMPANY_SIGNUP_WEBHOOK"]:
            # Call Integromat for Trello card creation
            try:
                first_establishment_info = (
                    company.siren_api_info[0]
                    if company.siren_api_info
                    and len(company.siren_api_info) > 0
                    else None
                )
                response = requests.post(
                    app.config["INTEGROMAT_COMPANY_SIGNUP_WEBHOOK"],
                    data=dict(
                        name=company.name,
                        creation_time=company.creation_time,
                        submitter_name=current_user.display_name,
                        submitter_email=current_user.email,
                        siren=company.siren,
                        metabase_link=f"{app.config['METABASE_COMPANY_DASHBOARD_BASE_URL']}{company.id}",
                        location=f"{first_establishment_info.get('address', '')} {first_establishment_info.get('postal_code', '')}"
                        if first_establishment_info
                        else None,
                    ),
                    timeout=3,
                )
                if not response.status_code == 200:
                    app.logger.warning(
                        f"Creation of Trello card for {company} failed with error : {response.text}"
                    )
            except Exception as e:
                app.logger.warning(
                    f"Creation of Trello card for {company} failed with error : {e}"
                )

        return CompanySignUp(company=company, employment=admin_employment)


class NonPublicQuery(graphene.ObjectType):
    siren_info = graphene.Field(
        GenericScalar,
        siren=graphene.Int(required=True, description="SIREN de l'entreprise"),
        description="Interrogation de l'API SIRENE pour récupérer la liste des établissements associés à un SIREN",
    )

    def resolve_siren_info(self, info, siren):
        return siren_api_client.get_siren_info(siren)


class Query(graphene.ObjectType):
    company = graphene.Field(
        CompanyOutput,
        id=graphene.Int(
            required=True, description="Identifiant de l'entreprise"
        ),
        description="Consultation des données de l'entreprise, avec notamment la liste de ses membres (et leurs enregistrements)",
    )

    @with_authorization_policy(
        belongs_to_company_at,
        get_target_from_args=lambda self, info, id: id,
        error_message="Forbidden access",
    )
    def resolve_company(self, info, id):
        matching_company = Company.query.get(id)
        return matching_company


@app.route("/download_company_activity_report", methods=["POST"])
def download_activity_report():
    try:
        company_ids = request.args.get("company_ids")
        company_ids = [int(cid) for cid in company_ids.split(",")]
        if not company_ids:
            raise Exception
    except:
        return jsonify({"error": "invalid company ids"}), 400

    try:
        user_ids = request.args.get("user_ids")
        user_ids = [int(uid) for uid in user_ids.split(",")]
    except Exception:
        user_ids = []

    try:
        min_date = request.args.get("min_date")
        min_date = date.fromisoformat(min_date)
    except Exception:
        min_date = None

    try:
        max_date = request.args.get("max_date")
        max_date = date.fromisoformat(max_date)
    except Exception:
        max_date = None

    try:
        require_auth()()
    except AuthenticationError as e:
        return jsonify({"error": e.message}), 401

    if not set(company_ids) <= set(
        current_user.current_company_ids_with_admin_rights
    ):
        return jsonify({"error": "Forbidden access"}), 403

    companies = (
        Company.query.options(
            selectinload(Company.employments).selectinload(Employment.user)
        )
        .filter(Company.id.in_(company_ids))
        .all()
    )

    app.logger.info(f"Downloading activity report for {companies}")
    all_users_work_days = []
    all_users = set([user for company in companies for user in company.users])
    if user_ids:
        all_users = [u for u in all_users if u.id in user_ids]
    for user in all_users:
        all_users_work_days += group_user_events_by_day(
            user,
            ConsultationScope(company_ids=company_ids),
            from_date=min_date,
            until_date=max_date,
        )

    return send_work_days_as_excel(all_users_work_days)
