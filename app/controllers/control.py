from flask import Blueprint, jsonify, request

from app.helpers.authentication import require_auth_with_write_access
from app.helpers.authorization import (
    with_authorization_policy,
    active,
    current_user,
)
from app.helpers.errors import BadRequestError
from app.helpers.xls import (
    retrieve_and_verify_signature,
)
from app.models import UserReadToken


FILE_NAME = "xlsx-to-check"

control_blueprint = Blueprint("control", __name__)


@control_blueprint.route("/generate-user-read-token", methods=["POST"])
@with_authorization_policy(active)
@require_auth_with_write_access
def generate_read_token():
    token = UserReadToken.get_or_create(current_user)
    return jsonify({"token": token.token})


@control_blueprint.route("/verify-xlsx-signature", methods=["POST"])
def verify_xlsx_signature():
    if FILE_NAME not in request.files:
        raise BadRequestError(
            f"Could not find file with name {FILE_NAME} in request"
        )
    file = request.files[FILE_NAME]
    retrieve_and_verify_signature(file)
    return {"success": True}
