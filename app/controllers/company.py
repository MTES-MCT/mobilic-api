import graphene
from sqlalchemy.orm import joinedload

from app.data_access.signup import CompanyOutput
from app.domain.permissions import belongs_to_company, company_admin
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import with_authorization_policy
from app.helpers.xls import send_work_days_as_excel
from app.models import Company, User
from app import db, app


def _query_company_with_relations(id):
    return Company.query.options(
        joinedload(Company.users).joinedload(User.activities)
    ).get(id)


class CompanySignup(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)

    company = graphene.Field(CompanyOutput)

    @classmethod
    def mutate(cls, _, info, name):
        company = Company(name=name)
        db.session.add(company)
        db.session.commit()
        return CompanySignup(company=company)


class Query(graphene.ObjectType):
    company = graphene.Field(CompanyOutput, id=graphene.Int(required=True))

    @with_authorization_policy(
        belongs_to_company, get_target_from_args=lambda self, info, id: id
    )
    def resolve_company(self, info, id):
        matching_company = _query_company_with_relations(id)
        return matching_company


@app.route("/api/download_company_activity_report/<int:id>")
@with_authorization_policy(
    company_admin, get_target_from_args=lambda id, *args, **kwargs: id
)
def download_activity_report(id):
    company = _query_company_with_relations(id)
    all_users_work_days = []
    for user in company.users:
        all_users_work_days += group_user_events_by_day(user)

    return send_work_days_as_excel(all_users_work_days)
