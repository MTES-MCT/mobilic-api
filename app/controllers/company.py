from flask_restful import Resource

from app.controllers.utils import (
    parse_request_with_schema,
    request_data_schema,
)
from app.models import Company
from app import db


@request_data_schema
class CompanySignupData:
    name: str


class CompanyController(Resource):
    @parse_request_with_schema(CompanySignupData)
    def post(self, data):
        try:
            company = Company(name=data.name)
            db.session.add(company)
            db.session.commit()
        except Exception as e:
            raise e
