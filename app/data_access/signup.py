from graphene_sqlalchemy import SQLAlchemyObjectType

from app.controllers.utils import request_data_schema
from app.models import User, Company


@request_data_schema
class SignupPostData:
    email: str
    password: str
    first_name: str
    last_name: str
    company_id: int


@request_data_schema
class CompanySignupData:
    name: str


class UserOutput(SQLAlchemyObjectType):
    class Meta:
        model = User
        only_fields = ("id", "first_name", "last_name", "company")


class CompanyOutput(SQLAlchemyObjectType):
    class Meta:
        model = Company
