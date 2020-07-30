import graphene
from flask import request
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from graphene.types.generic import GenericScalar

from app.controllers.utils import atomic_transaction
from app.data_access.company import CompanyOutput
from app.domain.permissions import (
    belongs_to_company_at,
    company_admin_at,
    ConsultationScope,
)
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated,
    current_user,
)
from app import siren_api_client
from app.helpers.errors import SirenAlreadySignedUpError
from app.helpers.xls import send_work_days_as_excel
from app.models import Company, Employment
from app.models.employment import (
    EmploymentRequestValidationStatus,
    EmploymentOutput,
)
from app.models.queries import (
    company_query_with_users_and_activities,
    company_queries_with_all_relations,
)
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

            try:
                db.session.flush()
            except IntegrityError as e:
                if e.orig.pgcode == "23505":  # Unique violation
                    print("f")
                    raise SirenAlreadySignedUpError("SIREN already registered")
                raise e

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

            app.logger.info(f"Signed up new company {company}")

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
        belongs_to_company_at, get_target_from_args=lambda self, info, id: id
    )
    def resolve_company(self, info, id):
        matching_company = (
            company_query_with_users_and_activities()
            .filter(Company.id == id)
            .one()
        )
        return matching_company


@app.route("/download_company_activity_report/<int:id>")
@with_authorization_policy(
    company_admin_at, get_target_from_args=lambda id, *args, **kwargs: id
)
def download_activity_report(id):
    try:
        min_date = request.args.get("min_date")
        min_date = datetime.fromisoformat(min_date)
    except Exception:
        min_date = None

    try:
        max_date = request.args.get("max_date")
        max_date = datetime.fromisoformat(max_date)
    except Exception:
        max_date = None

    company = (
        company_queries_with_all_relations().filter(Company.id == id).one()
    )
    app.logger.info(f"Downloading activity report for {company}")
    all_users_work_days = []
    for user in company.users:
        all_users_work_days += group_user_events_by_day(
            user, ConsultationScope(company_ids=[company.id])
        )

    if min_date:
        all_users_work_days = [
            wd
            for wd in all_users_work_days
            if not wd.end_time or wd.end_time >= min_date
        ]
    if max_date:
        all_users_work_days = [
            wd
            for wd in all_users_work_days
            if wd.start_time and wd.start_time.date() <= max_date.date()
        ]
    return send_work_days_as_excel(all_users_work_days)
