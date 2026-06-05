from datetime import timedelta

from flask_jwt_extended import create_access_token

from app import app
from app.helpers.errors import (
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

    The JWT subject stays the admin (id=admin.id) and the impersonation
    target is carried in the impersonate_as claim. The admin's own
    revocation rules apply to the session, so target-side revocations
    (e.g. password reset) do not break the impersonation.
    """
    target_user = User.query.get(target_user_id)
    if not target_user:
        raise InvalidParamsError("Target user not found")
    if target_user.id == admin_user.id:
        raise InvalidParamsError("Cannot impersonate yourself")
    if target_user.admin:
        raise AuthorizationError("Cannot impersonate another admin")

    access_token = create_access_token(
        {
            "id": admin_user.id,
            "impersonate_as": target_user.id,
        },
        expires_delta=IMPERSONATION_EXPIRATION,
    )
    return {
        "access_token": access_token,
        "impersonated_user_id": target_user.id,
    }


def create_admin_restore_token(admin_user):
    """Create a regular access token for the admin (used to stop impersonation)."""
    return create_access_token(
        {"id": admin_user.id},
        expires_delta=app.config["ACCESS_TOKEN_EXPIRATION"],
    )
