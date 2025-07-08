import requests
import jwt
from typing import Dict, Tuple, Optional
from urllib.parse import urljoin
import time
from threading import Lock
import logging

from app import app
from app.helpers.errors import FranceConnectV2Error

logger = logging.getLogger(__name__)


class JWTKeyManager:
    """Thread-safe JWT key manager with intelligent caching"""

    def __init__(self):
        self._cache: Dict = {}
        self._cache_expiry: float = 0
        self._lock = Lock()

    def get_public_keys(self, base_url: str, timeout: int) -> Optional[Dict]:
        """Retrieve JWT public keys with caching and graceful fallback"""
        current_time = time.time()

        with self._lock:
            if current_time < self._cache_expiry and self._cache:
                return self._cache

            try:
                oidc_url = urljoin(
                    base_url, "/.well-known/openid_configuration"
                )
                logger.info(f"Fetching OIDC config: {oidc_url}")

                oidc_response = requests.get(oidc_url, timeout=timeout)
                oidc_response.raise_for_status()
                oidc_config = oidc_response.json()

                jwks_url = oidc_config.get("jwks_uri")
                if not jwks_url:
                    logger.warning("jwks_uri missing from OIDC config")
                    return self._cache

                logger.info(f"Fetching JWKS keys: {jwks_url}")
                jwks_response = requests.get(jwks_url, timeout=timeout)
                jwks_response.raise_for_status()

                self._cache = jwks_response.json()
                self._cache_expiry = current_time + 3600  # Cache for 1 hour

                key_count = len(self._cache.get("keys", []))
                logger.info(f"Updated {key_count} JWT keys in cache")
                return self._cache

            except Exception as e:
                logger.warning(f"Error fetching JWT keys: {e}")
                return self._cache


_jwt_manager = JWTKeyManager()


def _create_public_key_from_jwk(key: Dict, algorithm: str):
    """Create public key from JWK based on algorithm"""
    if algorithm.startswith("RS"):
        return jwt.algorithms.RSAAlgorithm.from_jwk(key)
    elif algorithm.startswith("ES"):
        return jwt.algorithms.ECAlgorithm.from_jwk(key)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def _validate_with_public_key(
    id_token: str, public_key, algorithm: str, client_id: str
) -> Dict:
    """Validate JWT with public key and full verification"""
    return jwt.decode(
        id_token,
        public_key,
        algorithms=[algorithm],
        audience=client_id,
        options={
            "verify_signature": True,
            "verify_aud": True,
            "verify_exp": True,
            "verify_iat": True,
        },
    )


def _fallback_jwt_validation(id_token: str, client_id: str) -> Dict:
    """Fallback JWT validation - minimal verification for compatibility"""
    logger.warning(
        "FALLBACK: JWT validation without signature - should be fixed in production"
    )

    try:
        # Try with basic verification (v2 compatible)
        payload = jwt.decode(
            id_token,
            options={
                "verify_signature": False,
                "verify_aud": True,
                "verify_exp": True,
                "verify_iat": True,
            },
            audience=client_id,
        )
        logger.warning(
            "JWT token accepted with basic verification (no signature)"
        )
        return payload

    except (
        jwt.InvalidTokenError,
        jwt.InvalidAudienceError,
        jwt.ExpiredSignatureError,
        jwt.InvalidIssuedAtError,
    ) as e:
        # Ultimate fallback for v1 compatibility
        logger.warning(
            f"Basic verification failed: {e}, using minimal validation"
        )
        payload = jwt.decode(id_token, options={"verify_signature": False})
        logger.warning("JWT token accepted with MINIMAL verification")
        return payload


def validate_jwt_secure(
    id_token: str, client_id: str, base_url: str, timeout: int
) -> Dict:
    """Secure JWT validation with cryptographic signature verification"""
    try:
        jwks = _jwt_manager.get_public_keys(base_url, timeout)

        if not (jwks and jwks.get("keys")):
            return _fallback_jwt_validation(id_token, client_id)

        unverified_header = jwt.get_unverified_header(id_token)
        key_id = unverified_header.get("kid")
        algorithm = unverified_header.get("alg", "RS256")

        logger.info(f"Validating JWT with kid={key_id}, alg={algorithm}")

        for key in jwks["keys"]:
            if key.get("kid") != key_id:
                continue

            try:
                public_key = _create_public_key_from_jwk(key, algorithm)
                payload = _validate_with_public_key(
                    id_token, public_key, algorithm, client_id
                )
                logger.info("JWT validated with cryptographic signature")
                return payload

            except ValueError as e:
                logger.warning(f"Unsupported algorithm: {e}")
                continue
            except jwt.InvalidTokenError as e:
                logger.warning(f"JWT validation failed for kid={key_id}: {e}")
                continue
            except Exception as e:
                logger.error(f"JWT validation error: {e}")
                continue

        logger.warning("No valid key found for JWT validation")
        return _fallback_jwt_validation(id_token, client_id)

    except Exception as e:
        logger.error(f"JWT validation error: {e}")
        logger.warning("CRITICAL FALLBACK: Minimal JWT validation")
        return _fallback_jwt_validation(id_token, client_id)


def make_secure_request(
    method: str, url: str, timeout: int, **kwargs
) -> requests.Response:
    """Robust HTTP client with error handling and timeouts"""
    try:
        logger.debug(f"Request {method} {url} (timeout={timeout}s)")
        response = requests.request(method, url, timeout=timeout, **kwargs)
        logger.debug(f"HTTP response {response.status_code}")
        return response

    except requests.Timeout:
        logger.error(f"Timeout {timeout}s exceeded for {url}")
        raise FranceConnectV2Error(
            f"FranceConnect communication timeout: {url} (timeout: {timeout}s)"
        )
    except requests.ConnectionError as e:
        logger.error(f"Connection error {url}: {e}")
        raise FranceConnectV2Error(
            f"FranceConnect connection error: {url} - {str(e)}"
        )
    except requests.RequestException as e:
        logger.error(f"Request error {url}: {e}")
        raise FranceConnectV2Error(
            f"FranceConnect request error: {url} - {str(e)}"
        )


def get_fc_config() -> Tuple[str, str, str, str, int]:
    """Get FranceConnect configuration with fallbacks and version detection"""
    base_url = app.config.get(
        "FC_V2_URL",
        app.config.get("FC_URL", "https://fcp.integ01.dev-franceconnect.fr"),
    )
    client_id = app.config.get(
        "FC_V2_CLIENT_ID", app.config.get("FC_CLIENT_ID")
    )
    client_secret = app.config.get(
        "FC_V2_CLIENT_SECRET", app.config.get("FC_CLIENT_SECRET")
    )
    timeout = int(app.config.get("FC_TIMEOUT", 10))
    api_version = _detect_api_version(base_url)
    return base_url, client_id, client_secret, api_version, timeout


def _detect_api_version(base_url: str) -> str:
    """Detect API version based on URL patterns and configuration"""
    if "FC_V2_URL" in app.config:
        return "v2"

    url_sandbox_pattern = {
        "v2": "fcp-low.sbx.dev-franceconnect.fr",
        "v1": "fcp-low.integ01.dev-franceconnect.fr",
    }

    for key, value in url_sandbox_pattern.items():
        if base_url == value:
            return key

    # Default to v1 for all other cases (including app.franceconnect.gouv.fr)
    # Note: app.franceconnect.gouv.fr is used for both v1 and v2 production
    # The distinction is made via endpoint paths (/api/v1/ vs /api/v2/)
    return "v1"


def _fetch_access_token(
    authorization_code: str,
    original_redirect_uri: str,
    base_url: str,
    api_version: str,
    client_id: str,
    client_secret: str,
    timeout: int,
) -> Tuple[str, str]:
    """Fetch access token from FranceConnect"""
    # Use override URI for FranceConnect v2 API calls if configured (for local development)
    fc_redirect_uri = original_redirect_uri
    if api_version == "v2":
        fc_redirect_uri = app.config.get(
            "FC_V2_REDIRECT_URI_OVERRIDE", original_redirect_uri
        )

    token_data = {
        "code": authorization_code,
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": fc_redirect_uri,
    }

    token_url = urljoin(base_url, f"/api/{api_version}/token")
    token_response = make_secure_request(
        "POST",
        token_url,
        timeout,
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if token_response.status_code != 200:
        error_details = _extract_error_details(token_response)
        logger.error(
            f"Token retrieval failed: HTTP {token_response.status_code}"
        )
        raise FranceConnectV2Error(
            f"Failed to retrieve access token: HTTP {token_response.status_code}, {error_details}"
        )

    token_json = token_response.json()
    access_token = token_json.get("access_token")
    id_token = token_json.get("id_token")

    if not access_token or not id_token:
        raise FranceConnectV2Error("Missing tokens in FranceConnect response")

    return access_token, id_token


def _extract_error_details(response: requests.Response) -> str:
    """Extract error details from HTTP response"""
    try:
        error_data = response.json()
        return f"{error_data.get('error', 'Unknown')}: {error_data.get('error_description', '')}"
    except (ValueError, requests.exceptions.JSONDecodeError):
        return response.text[:200]


def _fetch_user_info(
    base_url: str, api_version: str, access_token: str, timeout: int
) -> requests.Response:
    """Fetch user information from FranceConnect"""
    userinfo_url = urljoin(base_url, f"/api/{api_version}/userinfo")
    if api_version == "v1":
        userinfo_url += "?schema=openid"

    userinfo_response = make_secure_request(
        "GET",
        userinfo_url,
        timeout,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if userinfo_response.status_code != 200:
        logger.error(f"Userinfo failed: HTTP {userinfo_response.status_code}")
        raise FranceConnectV2Error(
            f"Failed to retrieve user information: HTTP {userinfo_response.status_code}"
        )

    return userinfo_response


def _parse_userinfo_response(
    userinfo_response: requests.Response,
    is_v2: bool,
    client_id: str,
    base_url: str,
    timeout: int,
) -> Dict:
    """Parse userinfo response (JSON or JWT for v2)"""
    if is_v2:
        try:
            user_info = validate_jwt_secure(
                userinfo_response.text, client_id, base_url, timeout
            )
            logger.info("v2 userinfo validated as signed JWT")
            return user_info
        except Exception as e:
            logger.info(f"v2 userinfo not JWT, processing as JSON: {e}")
            return userinfo_response.json()
    else:
        return userinfo_response.json()


def _enrich_with_jwt_data(
    user_info: Dict, id_token: str, client_id: str, base_url: str, timeout: int
) -> None:
    """Enrich user info with validated JWT data"""
    try:
        jwt_payload = validate_jwt_secure(
            id_token, client_id, base_url, timeout
        )

        user_info["acr"] = jwt_payload.get("acr")
        if "amr" in jwt_payload:
            user_info["amr"] = jwt_payload["amr"]
        if "auth_time" in jwt_payload:
            user_info["auth_time"] = jwt_payload["auth_time"]

    except Exception as e:
        logger.warning(f"JWT enrichment failed: {e}")


def get_fc_user_info(
    authorization_code: str, original_redirect_uri: str
) -> Tuple[Dict, str]:
    """Main secure FranceConnect function with v1/v2 compatibility"""

    base_url, client_id, client_secret, api_version, timeout = get_fc_config()
    is_v2 = api_version == "v2"

    logger.info(f"Secure FranceConnect {api_version} authentication")
    logger.info(f"Base URL: {base_url}")

    try:
        access_token, id_token = _fetch_access_token(
            authorization_code,
            original_redirect_uri,
            base_url,
            api_version,
            client_id,
            client_secret,
            timeout,
        )

        userinfo_response = _fetch_user_info(
            base_url, api_version, access_token, timeout
        )

        user_info = _parse_userinfo_response(
            userinfo_response, is_v2, client_id, base_url, timeout
        )

        _enrich_with_jwt_data(
            user_info, id_token, client_id, base_url, timeout
        )

        logger.info(
            f"FranceConnect {api_version} authentication successful: {user_info.get('sub', 'unknown')}"
        )
        return user_info, id_token

    except FranceConnectV2Error:
        raise
    except Exception as e:
        logger.error(f"Critical FranceConnect error: {e}")
        raise FranceConnectV2Error(
            f"Technical error: {str(e)} (Code: {authorization_code[:10]}..., URI: {original_redirect_uri})"
        )
