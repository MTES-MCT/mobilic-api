from flask import Blueprint, jsonify, request

from app.helpers.authorization import (
    with_authorization_policy,
    authenticated_and_active,
    current_user,
)
from app.helpers.xls import (
    retrieve_and_verify_signature,
    IntegrityVerificationError,
)
from app.models import UserReadToken


FILE_NAME = "xlsx-to-check"

control_blueprint = Blueprint(__name__, "app.controllers.control")


@control_blueprint.route("/generate-user-read-token", methods=["POST"])
@with_authorization_policy(authenticated_and_active)
def generate_read_token():
    token = UserReadToken.get_or_create(current_user)
    return jsonify({"token": token.token})


@control_blueprint.route("/verify-xlsx-signature", methods=["POST"])
def verify_xlsx_signature():
    if FILE_NAME not in request.files:
        return jsonify({"error": "MISSING_FILE"}), 400
    file = request.files[FILE_NAME]
    try:
        retrieve_and_verify_signature(file)
        return {"success": True}
    except IntegrityVerificationError as e:
        return jsonify({"error": e.code})
