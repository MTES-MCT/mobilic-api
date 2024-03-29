import requests
import json
import jwt

from app import app
from app.helpers.errors import FranceConnectAuthenticationError


# This is the second part of the OAuth protocol for FranceConnect, after the user logged in and we get an authorization code from FranceConnect.
# Whole flow is detailed here : https://partenaires.franceconnect.gouv.fr/fcp/fournisseur-service
def get_fc_user_info(authorization_code, original_redirect_uri):
    data = {
        "code": authorization_code,
        "grant_type": "authorization_code",
        "client_id": app.config["FC_CLIENT_ID"],
        "client_secret": app.config["FC_CLIENT_SECRET"],
        "redirect_uri": original_redirect_uri,
    }

    token_response = requests.post(
        f"{app.config['FC_URL']}/api/v1/token", data=data
    )

    if token_response.status_code != 200:
        raise FranceConnectAuthenticationError(
            "Unable to get a token from the authorization code"
        )

    token_response_json = token_response.json()
    id_token = token_response_json["id_token"]

    user_info_response = requests.get(
        f"{app.config['FC_URL']}/api/v1/userinfo?schema=openid",
        headers={
            "Authorization": "Bearer " + token_response.json()["access_token"]
        },
    )

    if user_info_response.status_code != 200:
        raise FranceConnectAuthenticationError(
            "Unable to get user info from token"
        )

    try:
        user_info = json.loads(user_info_response.content.decode("utf-8"))
    except json.decoder.JSONDecodeError:
        raise FranceConnectAuthenticationError("Unable to parse user info")

    user_info["acr"] = jwt.decode(
        id_token, algorithms=["HS256"], options={"verify_signature": False}
    ).get("acr")
    return user_info, id_token
