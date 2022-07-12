from urllib.parse import quote, urlencode, unquote
from uuid import uuid4

import graphene
from flask import redirect, request, after_this_request

from app import app
from app.controllers.utils import atomic_transaction
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
)
from app.helpers.authentication_controller import (
    create_access_tokens_for_controller,
    set_controller_auth_cookies,
)


@app.route("/ac/authorize")
def redirect_to_ac_authorize():
    query_params = {
        "state": uuid4().hex,
        "nonce": uuid4().hex,
        "response_type": "code",
        # "scope": "openid profile email given_name usual_name organizational_unit",
        "scope": "openid email given_name family_name preferred_username birthdate",
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

        redirect_uri = request.args.get("post_logout_redirect_uri")
        return redirect(unquote(redirect_uri), code=302)

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
                response, user_id=controller.id, **tokens, ac_token=ac_token
            )
            return response

        return UserTokensWithAC(**tokens, ac_token=ac_token)
