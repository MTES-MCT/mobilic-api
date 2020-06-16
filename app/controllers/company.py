import graphene
from flask import request
from datetime import datetime

from app.data_access.company import CompanyOutput
from app.domain.permissions import belongs_to_company, company_admin
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import with_authorization_policy
from app.helpers.xls import send_work_days_as_excel
from app.models import Company, User
from app.models.queries import (
    company_query_with_users_and_activities,
    company_queries_with_all_relations,
)
from app import db, app


class CompanySignUp(graphene.Mutation):
    """
    [NON EXPOSE POUR L'INSTANT]
    Inscription d'une nouvelle entreprise.

    Retourne l'entreprise nouvellement créée
    """

    class Arguments:
        name = graphene.String(
            required=True, description="Nom de l'entreprise"
        )

    Output = CompanyOutput

    @classmethod
    def mutate(cls, _, info, name):
        company = Company(name=name)
        try:
            db.session.add(company)
            db.session.commit()
            app.logger.info(f"Signed up new company {company}")
        except Exception as e:
            app.logger.exception(f"Error during company signup for {company}")
        return company


class Query(graphene.ObjectType):
    company = graphene.Field(
        CompanyOutput,
        id=graphene.Int(
            required=True, description="Identifiant de l'entreprise"
        ),
        description="Consultation des données de l'entreprise, avec notamment la liste de ses membres (et leurs enregistrements)",
    )

    @with_authorization_policy(
        belongs_to_company, get_target_from_args=lambda self, info, id: id
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
    company_admin, get_target_from_args=lambda id, *args, **kwargs: id
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
        all_users_work_days += group_user_events_by_day(user)

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
