from flask_restful import Resource
from flask import jsonify

from app.controllers.utils import parse_request_with_schema, atomic_transaction
from app.data_access.signup import SignupPostData
from app.models import User
from app import db


class UserController(Resource):
    @parse_request_with_schema(SignupPostData)
    def post(self, data):
        try:
            user = User(**data.to_dict())
            db.session.add(user)
            db.session.commit()
            return jsonify(user)
        except Exception as e:
            raise e
