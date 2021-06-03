from webargs.flaskparser import FlaskParser
from flask import abort, jsonify


class CustomRequestParser(FlaskParser):
    def handle_error(
        self, error, req, schema, *, error_status_code, error_headers
    ):
        status_code = error_status_code or self.DEFAULT_VALIDATION_STATUS
        response = jsonify({"parsing_error": error.messages})
        response.status_code = status_code
        abort(response)

    def _handle_invalid_json_error(self, error, req, *args, **kwargs):
        response = jsonify({"parsing_error": error.messages})
        response.status_code = 400
        abort(response)
