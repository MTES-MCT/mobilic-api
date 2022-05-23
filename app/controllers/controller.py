from urllib.parse import quote, urlencode
from uuid import uuid4

import graphene
from flask import redirect, request, after_this_request

from app import app
from app.controllers.utils import atomic_transaction
from app.domain.user import create_user
from app.helpers.agent_connect import (
    get_agent_connect_user_info,
    get_controller_from_ac_info,
)
from app.helpers.authentication import (
    create_access_tokens_for,
    UserTokensWithFC,
    set_auth_cookies,
)


@app.route("/ac/authorize")
def redirect_to_ac_authorize():
    query_params = {
        "state": uuid4().hex,
        "nonce": uuid4().hex,
        "scope": "openid profile email",
        "client_id": app.config["AC_CLIENT_ID"],
        "acr_values": "eidas1",
    }
    return redirect(
        f"{app.config['AC_URL']}?{request.query_string.decode('utf-8')}&{urlencode(query_params, quote_via=quote)}",
        code=302,
    )


class AgentConnectLogin(graphene.Mutation):
    class Arguments:
        authorization_code = graphene.String(required=True)
        state = graphene.String(required=True)
        original_redirect_uri = graphene.String(required=True)
        create = graphene.Boolean(required=False)

    Output = UserTokensWithFC

    @classmethod
    def mutate(
        cls,
        _,
        info,
        authorization_code,
        original_redirect_uri,
        state,
        invite_token=None,
        create=False,
    ):
        with atomic_transaction(commit_at_end=True):
            ac_user_info, ac_token = get_agent_connect_user_info(
                authorization_code, original_redirect_uri
            )
            user = get_controller_from_ac_info(ac_user_info)

            if not user:
                user = create_user(
                    first_name=ac_user_info.get("given_name"),
                    last_name=ac_user_info.get("family_name"),
                    email=ac_user_info.get("email"),
                    invite_token=invite_token,
                    fc_info=ac_user_info,
                )

        tokens = create_access_tokens_for(user)

        @after_this_request
        def set_cookies(response):
            set_auth_cookies(
                response, user_id=user.id, **tokens, fc_token=ac_token
            )
            return response

        return UserTokensWithFC(**tokens, fc_token=ac_token)
