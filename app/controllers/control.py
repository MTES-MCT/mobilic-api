import time

import graphene
from flask import Blueprint, jsonify, request
import jwt
from flask_apispec import doc, use_kwargs
from webargs import fields

from app import app, db
from app.data_access.control_data import ControllerControlOutput
from app.domain.permissions import controller_can_see_control
from app.helpers.authentication import require_auth_with_write_access
from app.helpers.authorization import (
    with_authorization_policy,
    active,
    current_user,
    controller_only,
)
from app.helpers.errors import BadRequestError
from app.helpers.s3 import S3Client
from app.helpers.xls import (
    retrieve_and_verify_signature,
)
from app.models import UserReadToken
from app.models.controller_control import ControllerControl

FILE_NAME = "xlsx-to-check"

control_blueprint = Blueprint("control", __name__)


@control_blueprint.route("/generate-user-read-token", methods=["POST"])
@with_authorization_policy(active)
@require_auth_with_write_access
def generate_read_token():
    token = UserReadToken.get_or_create(current_user)
    jwt_token = jwt.encode(
        {"userId": current_user.id, "dateCodeGeneration": time.time()},
        app.config["CONTROL_SIGNING_KEY"],
        algorithm="HS256",
    )
    return jsonify({"token": token.token, "controlToken": jwt_token})


@control_blueprint.route("/verify-xlsx-signature", methods=["POST"])
def verify_xlsx_signature():
    if FILE_NAME not in request.files:
        raise BadRequestError(
            f"Could not find file with name {FILE_NAME} in request"
        )
    file = request.files[FILE_NAME]
    retrieve_and_verify_signature(file)
    return {"success": True}


class AddControlNote(graphene.Mutation):
    class Arguments:
        control_id = graphene.Int(required=True)
        content = graphene.Argument(graphene.String, required=True)

    Output = ControllerControlOutput

    @classmethod
    @with_authorization_policy(
        controller_can_see_control,
        get_target_from_args=lambda *args, **kwargs: kwargs["control_id"],
    )
    def mutate(cls, _, info, control_id, content):
        control = ControllerControl.query.get(control_id)
        control.note = content
        db.session.commit()
        return control


@app.route(
    "/controllers/control-pictures-generate-presigned-urls", methods=["POST"]
)
@doc(
    description="Génération d'url à durée limitée pour uploader les images d'un contrôle"
)
@with_authorization_policy(controller_only)
@use_kwargs(
    {
        "control_id": fields.Int(required=True),
        "nb_pictures": fields.Int(required=True),
    },
    apply=True,
)
def control_pictures_generate_presigned_urls(control_id, nb_pictures):
    presigned_urls = S3Client.generated_presigned_urls_for_control(
        control_id, nb_pictures
    )
    return jsonify({"presigned-urls": presigned_urls})
