from flask_restful import Api

from app import app
from .user import UserController
from .activity import ActivityController
from .company import CompanyController


api = Api(app, prefix="/api")
api.add_resource(UserController, "/users")
api.add_resource(ActivityController, "/activities")
api.add_resource(CompanyController, "/companies")
