"""
FranceConnect V2 Authentication
"""

import json
import logging
from typing import Dict, Tuple
from urllib.parse import urlencode, quote

import jwt
import requests
from jwt import PyJWKClient

from app import app
from app.helpers.errors import (
    FranceConnectV2Error,
    InvalidJwtTokenFormatError,
)

logger = logging.getLogger(__name__)


def get_fc_user_info(
    authorization_code: str, original_redirect_uri: str
) -> Tuple[Dict, str]:
    logger.info("=== FRANCECONNECT V2 AUTHENTICATION START ===")
    logger.info(
        f"Authorization code: {authorization_code[:20] if authorization_code else 'None'}..."
    )
    logger.info(f"Original redirect URI: {original_redirect_uri}")

    if not authorization_code or not isinstance(authorization_code, str):
        raise ValueError("Invalid authorization code")
    if not original_redirect_uri or not isinstance(original_redirect_uri, str):
        raise ValueError("Invalid redirect URI")

    base_url = app.config["FC_V2_URL"]
    client_id = app.config["FC_V2_CLIENT_ID"]
    client_secret = app.config["FC_V2_CLIENT_SECRET"]
    logger.info(f"Using FranceConnect V2: {base_url}")

    redirect_uri = original_redirect_uri
    if app.config.get("MOBILIC_ENV") != "prod" and app.config.get(
        "FC_V2_REDIRECT_URI_OVERRIDE"
    ):
        redirect_uri = app.config["FC_V2_REDIRECT_URI_OVERRIDE"]
        logger.info(f"Using override URI: {redirect_uri}")

    token_data = {
        "code": authorization_code,
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }

    token_response = requests.post(f"{base_url}/api/v2/token", data=token_data)

    if token_response.status_code != 200:
        error_msg = (
            f"Token exchange failed with status {token_response.status_code}"
        )
        try:
            error_data = token_response.json()
            error_detail = f"{error_data.get('error', 'unknown')}: {error_data.get('error_description', 'no description')}"
            error_msg += f" - {error_detail}"
        except:
            error_msg += f" - {token_response.text[:200]}"

        logger.error(error_msg)
        raise FranceConnectV2Error(error_msg)

    try:
        token_json = token_response.json()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from token endpoint: {e}")
        raise FranceConnectV2Error("Invalid token response format")

    if "access_token" not in token_json or "id_token" not in token_json:
        missing = []
        if "access_token" not in token_json:
            missing.append("access_token")
        if "id_token" not in token_json:
            missing.append("id_token")
        error_msg = f"Missing tokens in response: {', '.join(missing)}"
        logger.error(error_msg)
        raise FranceConnectV2Error(error_msg)

    id_token = token_json["id_token"]
    access_token = token_json["access_token"]
    logger.info("Token exchange successful")

    user_info_response = requests.get(
        f"{base_url}/api/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"schema": "openid"},
    )

    if user_info_response.status_code != 200:
        error_msg = f"UserInfo request failed with status {user_info_response.status_code}"
        logger.error(error_msg)
        raise FranceConnectV2Error(error_msg)

    jwt_token_response = user_info_response.content.decode("utf-8")

    try:
        jwks_client = PyJWKClient(f"{base_url}/api/v2/jwks")
        signing_key = jwks_client.get_signing_key_from_jwt(jwt_token_response)
    except Exception as e:
        logger.error(f"Failed to get JWKS signing key: {e}")
        raise FranceConnectV2Error(f"Unable to retrieve JWT signing keys: {e}")

    try:
        user_info = jwt.decode(
            jwt_token_response,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience=client_id,
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT validation failed: {e}")
        raise InvalidJwtTokenFormatError(f"Invalid JWT token: {e}")
    except json.decoder.JSONDecodeError as e:
        logger.error(f"JSON decode failed: {e}")
        raise FranceConnectV2Error("Unable to parse user info as JSON")
    except Exception as e:
        logger.error(f"Unexpected JWT error: {e}")
        raise FranceConnectV2Error(f"JWT processing failed: {e}")

    try:
        id_payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience=client_id,
            options={"verify_exp": True},
        )
        user_info["acr"] = id_payload.get("acr")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Could not extract ACR from id_token: {e}")
        user_info["acr"] = None

    logger.info("=== FRANCECONNECT V2 AUTHENTICATION SUCCESS ===")
    return user_info, id_token


def get_fc_config() -> Tuple[str, str, str, str, int]:
    return (
        app.config["FC_V2_URL"],
        app.config["FC_V2_CLIENT_ID"],
        app.config["FC_V2_CLIENT_SECRET"],
        "v2",
        int(app.config.get("FC_TIMEOUT", 10)),
    )


def get_fc_logout_url(
    id_token: str, post_logout_redirect_uri: str, state: str
) -> str:
    base_url = app.config["FC_V2_URL"]

    params = {
        "id_token_hint": id_token,
        "post_logout_redirect_uri": post_logout_redirect_uri,
        "state": state,
    }

    return f"{base_url}/api/v2/session/end_session?{urlencode(params, quote_via=quote)}"
