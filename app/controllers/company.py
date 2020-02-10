import graphene
from sqlalchemy.orm import joinedload

from app.data_access.signup import CompanySignupData, CompanyOutput
from app.data_access.utils import with_input_from_schema
from app.domain.permissions import belongs_to_company
from app.helpers.authorization import with_authorization_policy
from app.models import Company, User
from app import db


@with_input_from_schema(CompanySignupData)
class CompanySignup(graphene.Mutation):
    company = graphene.Field(CompanyOutput)

    @classmethod
    def mutate(cls, _, info, input):
        company = Company(name=input.name)
        db.session.add(company)
        db.session.commit()
        return CompanySignup(company=company)


class Query(graphene.ObjectType):
    company = graphene.Field(CompanyOutput, id=graphene.Int(required=True))

    @with_authorization_policy(
        belongs_to_company, get_target_from_self=lambda self: self
    )
    def resolve_company(self, info, id):
        matching_company = Company.query.options(
            joinedload(Company.users).joinedload(User.activities)
        ).get(id)
        return matching_company
