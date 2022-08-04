from urllib.parse import quote, urlencode, unquote
from uuid import uuid4

import graphene
from flask import redirect, request, after_this_request, url_for

from app import app
from app.controllers.utils import atomic_transaction
from app.data_access.controller_user import ControllerUserOutput
from app.domain.controller import (
    create_controller_user,
    get_controller_from_ac_info,
)
from app.helpers.agent_connect import (
    get_agent_connect_user_info,
)
from app.helpers.authentication import (
    unset_ac_auth_cookies,
    UserTokensWithAC,
    current_user,
)
from app.helpers.authentication_controller import (
    create_access_tokens_for_controller,
    set_controller_auth_cookies,
)
from app.helpers.authorization import (
    with_authorization_policy,
    controller_only,
)
from app.helpers.errors import AuthorizationError
from app.models.controller_user import ControllerUser


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
        authorized_logout_redirect_urls = ("/", "/logout")
        app.logger.warning(
            "Attempt do disconnect from AgentConnect a user who is not logged in"
        )

        redirect_uri = request.args.get("post_logout_redirect_uri")
        if redirect_uri.endswith(authorized_logout_redirect_urls):
            return redirect(url_for(unquote(redirect_uri)), code=302)
        else:
            return redirect(unquote("/"), code=302)

    query_params = {"state": uuid4().hex, "id_token_hint": ac_token_hint}

    return redirect(
        f"{app.config['AC_LOGOUT_URL']}?{request.query_string.decode('utf-8')}&{urlencode(query_params, quote_via=quote)}",
        code=302,
    )


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

    @with_authorization_policy(
        controller_only,
        get_target_from_args=lambda *args, **kwargs: ControllerUser.query.get(
            kwargs["id"]
        ),
    )
    def resolve_controller_user(self, info, id):
        controller_user = ControllerUser.query.get(id)
        if not controller_user:
            raise AuthorizationError("Unknown controller id")
        if current_user.id != id:
            raise AuthorizationError("Can not view info of other Controller")
        return controller_user
