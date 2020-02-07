from dataclasses_json import dataclass_json
from dataclasses import dataclass
from flask_restful import Resource

from app.controllers.utils import parse_request_with_schema, atomic_transaction
from app.models import Company
from app import db


@dataclass_json
@dataclass
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
