import graphene

from app.data_access.signup import CompanySignupData, CompanyOutput
from app.data_access.utils import with_input_from_schema
from app.models import Company
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
