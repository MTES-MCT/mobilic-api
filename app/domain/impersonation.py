from datetime import timedelta

from flask import request
from flask_jwt_extended import create_access_token

from app import app
from app.helpers.errors import (
    AuthenticationError,
    AuthorizationError,
    InvalidParamsError,
)
from app.models import User


IMPERSONATION_EXPIRATION = timedelta(hours=2)


def validate_impersonation_prerequisites(admin_user):
    """Check that the admin has 2FA enabled and validated."""
    cred = admin_user.totp_credential
    if not cred or not cred.enabled:
        raise AuthorizationError("2FA must be enabled to use impersonation")


def create_impersonation_token(admin_user, target_user_id):
    """Create a JWT for impersonating a target user.

    Returns:
        dict with access_token and target user display info.
    """
    target_user = User.query.get(target_user_id)
    if not target_user:
        raise InvalidParamsError("Target user not found")

    access_token = create_access_token(
        {
            "id": target_user.id,
            "impersonate_by": admin_user.id,
        },
        expires_delta=IMPERSONATION_EXPIRATION,
    )
    return {
        "access_token": access_token,
        "impersonated_user_id": target_user.id,
    }


def get_admin_token_from_cookie():
    """Read the saved admin token from the admin_token cookie."""
    token = request.cookies.get("admin_token")
    if not token:
        raise AuthenticationError("No admin session to restore")
    return token
