from webargs.flaskparser import FlaskParser
from flask import abort, jsonify

from app.helpers.errors import InvalidParamsError, BadRequestError


class CustomRequestParser(FlaskParser):
    def handle_error(
        self, error, req, schema, *, error_status_code, error_headers
    ):
        raise InvalidParamsError(
            message="Parsing failed", extensions=error.messages
        )

    def _handle_invalid_json_error(self, error, req, *args, **kwargs):
        raise BadRequestError("Invalid json")
