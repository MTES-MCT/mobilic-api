from datetime import datetime
from urllib.parse import quote, unquote, urlencode
from uuid import uuid4

import graphene
import jwt
from flask import after_this_request, redirect, request, send_file
from flask_apispec import doc, use_kwargs
from marshmallow import Schema
from webargs import fields

from app import app, db
from app.controllers.user import TachographBaseOptionsSchema
from app.controllers.utils import atomic_transaction
from app.data_access.control_data import ControllerControlOutput
from app.data_access.controller_user import ControllerUserOutput
from app.domain.controller import (
    create_controller_user,
    get_controller_from_ac_info,
)
from app.domain.permissions import controller_can_see_control
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.agent_connect import get_agent_connect_user_info
from app.helpers.authentication import (
    UserTokensWithAC,
    current_user,
    unset_ac_auth_cookies,
)
from app.helpers.authentication_controller import (
    create_access_tokens_for_controller,
    set_controller_auth_cookies,
)
from app.helpers.authorization import (
    controller_only,
    with_authorization_policy,
)
from app.helpers.errors import AuthorizationError, InvalidControlToken
from app.helpers.pdf.control_bulletin import generate_control_bulletin_pdf
from app.helpers.pdf.mission_details import generate_mission_details_pdf
from app.helpers.tachograph import get_tachograph_archive_controller
from app.helpers.xls.controllers import send_control_as_one_excel_file
from app.models import Mission, ControlBulletin
from app.models.controller_control import ControllerControl, ControlType
from app.models.controller_user import ControllerUser
from app.models.queries import add_mission_relations, query_controls


@app.route("/ac/authorize")
def redirect_to_ac_authorize():
    query_params = {
        "state": uuid4().hex,
        "nonce": uuid4().hex,
        "response_type": "code",
        "scope": "openid uid email given_name usual_name organizational_unit",
        "client_id": app.config["AC_CLIENT_ID"],
        "acr_values": "eidas1",
    }
    return redirect(
        f"{app.config['AC_AUTHORIZE_URL']}?{request.query_string.decode('utf-8')}&{urlencode(query_params, quote_via=quote)}",
        code=302,
    )


@app.route("/ac/logout")
def redirect_to_ac_logout():
    ac_token_hint = request.cookies.get("act")

    @after_this_request
    def unset_ac_cookies(response):
        unset_ac_auth_cookies(response)
        return response

    if not ac_token_hint:
        app.logger.warning(
            "Attempt do disconnect from AgentConnect a user who is not logged in"
        )
        return redirect(unquote("/logout"), code=302)

    query_params = {"state": uuid4().hex, "id_token_hint": ac_token_hint}

    return redirect(
        f"{app.config['AC_LOGOUT_URL']}?{request.query_string.decode('utf-8')}&{urlencode(query_params, quote_via=quote)}",
        code=302,
    )


class ControllerScanCode(graphene.Mutation):
    class Arguments:
        jwt_token = graphene.String(required=True)

    Output = ControllerControlOutput

    @classmethod
    @with_authorization_policy(controller_only)
    def mutate(cls, _, info, jwt_token):
        try:
            decoded_token = jwt.decode(
                jwt_token,
                app.config["CONTROL_SIGNING_KEY"],
                algorithms="HS256",
            )
        except:
            raise InvalidControlToken
        control = ControllerControl.get_or_create_mobilic_control(
            controller_id=current_user.id,
            user_id=decoded_token["userId"],
            qr_code_generation_time=datetime.fromtimestamp(
                decoded_token["dateCodeGeneration"]
            ),
        )
        return control


class ControllerSaveControlBulletin(graphene.Mutation):
    Output = ControllerControlOutput

    class Arguments:
        control_id = graphene.Int(required=False)
        user_first_name = graphene.String(required=False)
        user_last_name = graphene.String(required=False)
        user_birth_date = graphene.Date(required=False)
        user_nationality = graphene.String(required=False)
        lic_paper_presented = graphene.Boolean(required=False)
        siren = graphene.String(required=False)
        company_name = graphene.String(required=False)
        company_address = graphene.String(required=False)
        vehicle_registration_number = graphene.String(required=False)
        vehicle_registration_country = graphene.String(required=False)
        mission_address_begin = graphene.String(required=False)
        mission_address_end = graphene.String(required=False)
        transport_type = graphene.String(required=False)
        articles_nature = graphene.String(required=False)
        license_number = graphene.String(required=False)
        license_copy_number = graphene.String(required=False)
        observation = graphene.String(required=False)

    @classmethod
    @with_authorization_policy(controller_only)
    def mutate(
        cls,
        _,
        info,
        control_id=None,
        user_first_name=None,
        user_last_name=None,
        user_nationality=None,
        lic_paper_presented=None,
        user_birth_date=None,
        siren=None,
        company_name=None,
        company_address=None,
        vehicle_registration_number=None,
        vehicle_registration_country=None,
        mission_address_begin=None,
        mission_address_end=None,
        transport_type=None,
        articles_nature=None,
        license_number=None,
        license_copy_number=None,
        observation=None,
    ):
        if control_id:
            controller_can_see_control(current_user, control_id)
            control = ControllerControl.query.filter(
                ControllerControl.id == control_id
            ).one()
        else:
            control = ControllerControl.create_no_lic_control(current_user.id)

        existing_bulletin = control.control_bulletin
        if not existing_bulletin:
            existing_bulletin = ControlBulletin(control_id=control.id)
            db.session.add(existing_bulletin)
            control.control_bulletin = existing_bulletin

        existing_bulletin.user_first_name = user_first_name
        existing_bulletin.user_last_name = user_last_name
        existing_bulletin.user_birth_date = user_birth_date
        existing_bulletin.user_nationality = user_nationality
        existing_bulletin.lic_paper_presented = lic_paper_presented
        existing_bulletin.siren = siren
        existing_bulletin.company_name = company_name
        existing_bulletin.company_address = company_address
        existing_bulletin.vehicle_registration_number = (
            vehicle_registration_number
        )
        existing_bulletin.vehicle_registration_country = (
            vehicle_registration_country
        )
        existing_bulletin.mission_address_begin = mission_address_begin
        existing_bulletin.mission_address_end = mission_address_end
        existing_bulletin.transport_type = transport_type
        existing_bulletin.articles_nature = articles_nature
        existing_bulletin.license_number = license_number
        existing_bulletin.license_copy_number = license_copy_number
        existing_bulletin.observation = observation
        db.session.commit()
        return control


class AgentConnectLogin(graphene.Mutation):
    class Arguments:
        authorization_code = graphene.String(required=True)
        state = graphene.String(required=True)
        original_redirect_uri = graphene.String(required=True)
        create = graphene.Boolean(required=False)

    Output = UserTokensWithAC

    @classmethod
    def mutate(
        cls,
        _,
        info,
        authorization_code,
        original_redirect_uri,
        state,
    ):
        with atomic_transaction(commit_at_end=True):
            ac_user_info, ac_token = get_agent_connect_user_info(
                authorization_code, original_redirect_uri
            )
            controller = get_controller_from_ac_info(ac_user_info)

            if not controller:
                controller = create_controller_user(ac_info=ac_user_info)

        tokens = create_access_tokens_for_controller(controller)

        @after_this_request
        def set_cookies(response):
            set_controller_auth_cookies(
                response,
                controller_user_id=controller.id,
                **tokens,
                ac_token=ac_token,
            )
            return response

        return UserTokensWithAC(**tokens, ac_token=ac_token)


class Query(graphene.ObjectType):
    controller_user = graphene.Field(
        ControllerUserOutput,
        id=graphene.Int(required=True),
        description="Consultation des informations d'un contrôleur",
    )

    control_data = graphene.Field(
        ControllerControlOutput,
        control_id=graphene.Int(required=True),
        description="Identifiant du contrôle à récupérer",
    )

    @with_authorization_policy(controller_only)
    def resolve_controller_user(self, info, id):
        controller_user = ControllerUser.query.get(id)
        if not controller_user:
            raise AuthorizationError("Unknown controller id")
        if current_user.id != id:
            raise AuthorizationError("Can not view info of other Controller")
        return controller_user

    @with_authorization_policy(
        controller_can_see_control,
        get_target_from_args=lambda *args, **kwargs: kwargs["control_id"],
    )
    def resolve_control_data(self, info, control_id):
        with atomic_transaction(commit_at_end=False):
            with db.session.no_autoflush:
                db.session().execute("SET CONSTRAINTS ALL DEFERRED")
                controller_control = ControllerControl.query.get(control_id)
                return controller_control


class MissionControlExportSchema(Schema):
    mission_id = fields.Int(required=True)
    control_id = fields.Int(required=True)


@app.route("/users/generate_mission_control_export", methods=["POST"])
@use_kwargs(MissionControlExportSchema, apply=True)
@with_authorization_policy(
    controller_can_see_control,
    get_target_from_args=lambda *args, **kwargs: kwargs["control_id"],
)
def generate_mission_control_export(mission_id, control_id):
    with atomic_transaction(commit_at_end=False):
        db.session().execute("SET CONSTRAINTS ALL DEFERRED")
        mission = add_mission_relations(Mission.query).get(mission_id)
        controller_control = ControllerControl.query.get(control_id)

        pdf = generate_mission_details_pdf(
            mission,
            controller_control.user,
            max_reception_time=controller_control.qr_code_generation_time,
        )

        return send_file(
            pdf,
            mimetype="application/pdf",
            as_attachment=True,
            cache_timeout=0,
            attachment_filename=f"Détails de la mission {mission.name or mission.id} pour {controller_control.user.display_name}",
        )


@app.route("/controllers/download_control_report", methods=["POST"])
@doc(description="Téléchargement du contrôle au format Excel")
@use_kwargs({"control_id": fields.Int(required=True)}, apply=True)
@with_authorization_policy(
    controller_can_see_control,
    get_target_from_args=lambda *args, **kwargs: kwargs["control_id"],
)
def download_control_report(control_id):
    control = ControllerControl.query.get(control_id)
    max_date = control.history_end_date
    min_date = control.history_start_date
    work_days_data = group_user_events_by_day_with_limit(
        control.user,
        from_date=min_date,
        until_date=max_date,
        include_dismissed_or_empty_days=True,
        max_reception_time=control.qr_code_generation_time,
    )[0]
    return send_control_as_one_excel_file(
        control, work_days_data, min_date, max_date
    )


@app.route("/controllers/generate_tachograph_files", methods=["POST"])
@doc(
    description="Génération de fichiers C1B contenant les données d'activité des salariés liés aux contrôles"
)
@with_authorization_policy(controller_only)
@use_kwargs(TachographBaseOptionsSchema(), apply=True)
def controller_download_tachograph_files(
    min_date, max_date, with_digital_signatures=False
):
    with atomic_transaction(commit_at_end=False):
        with db.session.no_autoflush:
            db.session().execute("SET CONSTRAINTS ALL DEFERRED")
            controls = query_controls(
                controller_user_id=current_user.id,
                start_time=min_date,
                end_time=max_date,
                controls_type=ControlType.mobilic,
            ).all()

            archive = get_tachograph_archive_controller(
                controls=controls, with_signatures=with_digital_signatures
            )
            return send_file(
                archive,
                mimetype="application/zip",
                as_attachment=True,
                cache_timeout=0,
                attachment_filename="fichiers_C1B.zip",
            )


@app.route("/controllers/generate_control_bulletin", methods=["POST"])
@doc(
    description="Génération d'un bulletin de contrôle en bord de route au format PDF"
)
@use_kwargs({"control_id": fields.Int(required=True)}, apply=True)
@with_authorization_policy(
    controller_can_see_control,
    get_target_from_args=lambda *args, **kwargs: kwargs["control_id"],
)
def generate_control_bulletin_pdf_export(control_id):
    control = ControllerControl.query.filter(
        ControllerControl.id == control_id
    ).one()

    pdf = generate_control_bulletin_pdf(control.control_bulletin)

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        cache_timeout=0,
        attachment_filename=f"bulletin",
    )
